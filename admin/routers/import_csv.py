"""
CSV-Import-Endpunkt.
Alle Imports sind idempotent: bereits vorhandene IDs werden übersprungen,
nicht überschrieben. So kann dieselbe CSV mehrfach importiert werden.
"""
import csv
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/import", tags=["import"])


def _parse_dt(s: str) -> datetime | None:
    """Parst ISO-8601-Timestamps (mit und ohne Offset)."""
    if not s or not s.strip():
        return None
    s = s.strip()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(f"Ungültiges Datum: '{s}'")


def _read_csv(upload: UploadFile) -> list[dict]:
    content = upload.file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return [row for row in reader]


# ── Units ─────────────────────────────────────────────────────────────────────
@router.post("/units", response_model=schemas.ImportResult)
def import_units(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Erwartete Spalten: id (optional), name
    """
    result = schemas.ImportResult()
    for row in _read_csv(file):
        try:
            name = row["name"].strip()
            existing = db.query(models.Unit).filter(models.Unit.name == name).first()
            if existing:
                result.skipped += 1
                continue
            db.add(models.Unit(name=name))
            result.created += 1
        except Exception as e:
            result.errors.append(f"Zeile {row}: {e}")
    db.commit()
    return result


# ── Residents ─────────────────────────────────────────────────────────────────
@router.post("/residents", response_model=schemas.ImportResult)
def import_residents(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Erwartete Spalten: id (optional, wird ignoriert), surname, givenname, email (opt.)
    """
    result = schemas.ImportResult()
    for row in _read_csv(file):
        try:
            r = models.Resident(
                surname=row["surname"].strip(),
                givenname=row["givenname"].strip(),
                email=row.get("email", "").strip() or None,
            )
            db.add(r)
            result.created += 1
        except Exception as e:
            result.errors.append(f"Zeile {row}: {e}")
    db.commit()
    return result


# ── Residencies ───────────────────────────────────────────────────────────────
@router.post("/residencies", response_model=schemas.ImportResult)
def import_residencies(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Erwartete Spalten: resident_id, unit, start, end
    'unit' ist die unit.id (Integer)
    """
    result = schemas.ImportResult()
    for row in _read_csv(file):
        try:
            unit_id     = int(row["unit"].strip())
            resident_id = int(row["resident_id"].strip())
            start       = _parse_dt(row["start"])
            end         = _parse_dt(row.get("end", ""))

            unit = db.get(models.Unit, unit_id)
            if not unit:
                result.errors.append(f"Unit {unit_id} nicht gefunden – Zeile übersprungen.")
                result.skipped += 1
                continue

            resident = db.get(models.Resident, resident_id)
            if not resident:
                result.errors.append(f"Resident {resident_id} nicht gefunden – Zeile übersprungen.")
                result.skipped += 1
                continue

            db.add(models.Residency(
                resident_id=resident_id, unit_id=unit_id,
                start_date=start, end_date=end
            ))
            result.created += 1
        except Exception as e:
            result.errors.append(f"Zeile {row}: {e}")
    db.commit()
    return result


# ── Meters ────────────────────────────────────────────────────────────────────
@router.post("/meters", response_model=schemas.ImportResult)
def import_meters(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Erwartete Spalten: type, id, unit (opt.), label (opt.), start, end (opt.)
    'type' ist der Name des MeterType (z.B. 'electricity')
    """
    result = schemas.ImportResult()
    for row in _read_csv(file):
        try:
            meter_id = row["id"].strip()

            # ID-Wiederverwendung ausschließen
            if db.get(models.Meter, meter_id):
                result.skipped += 1
                result.errors.append(
                    f"Meter '{meter_id}' bereits vorhanden – übersprungen (keine Wiederverwendung)."
                )
                continue

            # MeterType auflösen
            type_name = row["type"].strip().lower()
            mt = db.query(models.MeterType).filter(models.MeterType.name == type_name).first()
            if not mt:
                result.errors.append(f"Unbekannter MeterType '{type_name}' – Zeile übersprungen.")
                result.skipped += 1
                continue

            # Unit auflösen (optional)
            unit_id = None
            raw_unit = row.get("unit", "").strip()
            if raw_unit:
                unit_id = int(raw_unit)
                unit = db.get(models.Unit, unit_id)
                if not unit or not unit.active:
                    result.errors.append(
                        f"Unit {unit_id} für Meter '{meter_id}' nicht gefunden/inaktiv – übersprungen."
                    )
                    result.skipped += 1
                    continue

            start  = _parse_dt(row["start"])
            end    = _parse_dt(row.get("end", ""))
            label  = row.get("label", "").strip() or None

            db.add(models.Meter(
                id=meter_id, type_id=mt.id, unit_id=unit_id,
                label=label, start_date=start, end_date=end,
                active=(end is None)
            ))
            result.created += 1
        except Exception as e:
            result.errors.append(f"Zeile {row}: {e}")
    db.commit()
    return result