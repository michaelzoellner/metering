from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/residencies", tags=["residencies"])


def _check_overlap(unit_id: int, start_date, end_date, exclude_id: int | None, db: Session):
    """Stellt sicher, dass sich kein aktives Mietverhältnis für diese Unit überlappt."""
    q = (
        db.query(models.Residency)
        .filter(
            models.Residency.unit_id == unit_id,
            models.Residency.active == True,
        )
    )
    if exclude_id:
        q = q.filter(models.Residency.id != exclude_id)

    for res in q.all():
        res_end = res.end_date or datetime.max.replace(tzinfo=start_date.tzinfo)
        new_end = end_date or datetime.max.replace(tzinfo=start_date.tzinfo)
        # Überlappung: start1 < end2 AND start2 < end1
        if start_date < res_end and res.start_date < new_end:
            raise HTTPException(
                400,
                f"Überlappung mit bestehendem Mietverhältnis (ID {res.id}, "
                f"{res.start_date.date()} – {res.end_date.date() if res.end_date else 'offen'})."
            )


from datetime import datetime

@router.get("/", response_model=list[schemas.ResidencyRead])
def list_residencies(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Residency)
    if not include_inactive:
        q = q.filter(models.Residency.active == True)
    return q.order_by(models.Residency.start_date.desc()).all()


@router.get("/{residency_id}", response_model=schemas.ResidencyRead)
def get_residency(residency_id: int, db: Session = Depends(get_db)):
    r = db.get(models.Residency, residency_id)
    if not r:
        raise HTTPException(404, "Residency nicht gefunden")
    return r


@router.post("/", response_model=schemas.ResidencyRead, status_code=201)
def create_residency(body: schemas.ResidencyCreate, db: Session = Depends(get_db)):
    # Prüfen ob Unit und Resident existieren und aktiv sind
    unit = db.get(models.Unit, body.unit_id)
    if not unit or not unit.active:
        raise HTTPException(400, f"Unit {body.unit_id} existiert nicht oder ist inaktiv.")
    resident = db.get(models.Resident, body.resident_id)
    if not resident or not resident.active:
        raise HTTPException(400, f"Resident {body.resident_id} existiert nicht oder ist inaktiv.")

    _check_overlap(body.unit_id, body.start_date, body.end_date, None, db)

    r = models.Residency(**body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.patch("/{residency_id}", response_model=schemas.ResidencyRead)
def update_residency(residency_id: int, body: schemas.ResidencyUpdate, db: Session = Depends(get_db)):
    r = db.get(models.Residency, residency_id)
    if not r:
        raise HTTPException(404, "Residency nicht gefunden")

    new_end = body.end_date if body.end_date is not None else r.end_date
    _check_overlap(r.unit_id, r.start_date, new_end, residency_id, db)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return r