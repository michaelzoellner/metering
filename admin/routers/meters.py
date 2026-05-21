from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/meters", tags=["meters"])


def _assert_unit_exists_and_active(unit_id: int, db: Session):
    unit = db.get(models.Unit, unit_id)
    if not unit:
        raise HTTPException(400, f"Unit {unit_id} existiert nicht.")
    if not unit.active:
        raise HTTPException(400, f"Unit {unit_id} ist deaktiviert.")


@router.get("/", response_model=list[schemas.MeterRead])
def list_meters(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Meter)
    if not include_inactive:
        q = q.filter(models.Meter.active == True)
    return q.order_by(models.Meter.id).all()


@router.get("/{meter_id:path}", response_model=schemas.MeterRead)
def get_meter(meter_id: str, db: Session = Depends(get_db)):
    meter = db.get(models.Meter, meter_id)
    if not meter:
        raise HTTPException(404, "Meter nicht gefunden")
    return meter


@router.post("/", response_model=schemas.MeterRead, status_code=201)
def create_meter(body: schemas.MeterCreate, db: Session = Depends(get_db)):
    # Konsistenzprüfung 1: ID darf nie wiederverwendet werden
    existing = db.get(models.Meter, body.id)
    if existing:
        raise HTTPException(
            400,
            f"Meter-ID '{body.id}' existiert bereits "
            f"({'aktiv' if existing.active else 'inaktiv'}). "
            "IDs werden nie wiederverwendet."
        )
    # Konsistenzprüfung 2: unit_id muss existieren
    if body.unit_id is not None:
        _assert_unit_exists_and_active(body.unit_id, db)

    # Konsistenzprüfung 3: meter_type muss existieren
    mt = db.get(models.MeterType, body.type_id)
    if not mt:
        raise HTTPException(400, f"MeterType {body.type_id} unbekannt.")

    meter = models.Meter(**body.model_dump())
    db.add(meter)
    db.commit()
    db.refresh(meter)
    return meter


@router.patch("/{meter_id:path}", response_model=schemas.MeterRead)
def update_meter(meter_id: str, body: schemas.MeterUpdate, db: Session = Depends(get_db)):
    meter = db.get(models.Meter, meter_id)
    if not meter:
        raise HTTPException(404, "Meter nicht gefunden")

    # Deaktivierter Zähler darf nicht mehr verändert werden (außer Label/Kommentar)
    if not meter.active and body.active is not False:
        raise HTTPException(400, "Inaktiver Zähler kann nicht wieder aktiviert werden.")

    if body.unit_id is not None:
        _assert_unit_exists_and_active(body.unit_id, db)

    # Wenn deaktiviert wird: end_date muss gesetzt sein
    if body.active is False and meter.end_date is None and body.end_date is None:
        raise HTTPException(
            400, "Beim Deaktivieren eines Zählers muss end_date gesetzt sein."
        )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(meter, field, value)
    db.commit()
    db.refresh(meter)
    return meter