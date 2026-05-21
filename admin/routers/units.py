from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/units", tags=["units"])


@router.get("/", response_model=list[schemas.UnitRead])
def list_units(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Unit)
    if not include_inactive:
        q = q.filter(models.Unit.active == True)
    return q.order_by(models.Unit.id).all()


@router.get("/{unit_id}", response_model=schemas.UnitRead)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.get(models.Unit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit nicht gefunden")
    return unit


@router.post("/", response_model=schemas.UnitRead, status_code=201)
def create_unit(body: schemas.UnitCreate, db: Session = Depends(get_db)):
    # Doppelter Name ist durch DB-Unique-Constraint verhindert – trotzdem
    # schöne Fehlermeldung liefern
    existing = db.query(models.Unit).filter(models.Unit.name == body.name).first()
    if existing:
        if existing.active:
            raise HTTPException(400, f"Unit '{body.name}' existiert bereits (ID {existing.id})")
        raise HTTPException(
            400,
            f"Unit '{body.name}' existiert bereits als inaktiver Eintrag (ID {existing.id}). "
            "Bitte reaktivieren statt neu anlegen."
        )
    unit = models.Unit(**body.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.patch("/{unit_id}", response_model=schemas.UnitRead)
def update_unit(unit_id: int, body: schemas.UnitUpdate, db: Session = Depends(get_db)):
    unit = db.get(models.Unit, unit_id)
    if not unit:
        raise HTTPException(404, "Unit nicht gefunden")

    # Reaktivierung erlaubt; Deaktivierung nur wenn kein aktives Mietverhältnis
    if body.active is False:
        active_res = (
            db.query(models.Residency)
            .filter(models.Residency.unit_id == unit_id,
                    models.Residency.active == True,
                    models.Residency.end_date == None)
            .first()
        )
        if active_res:
            raise HTTPException(
                400,
                "Unit kann nicht deaktiviert werden: es besteht noch ein aktives Mietverhältnis."
            )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(unit, field, value)
    db.commit()
    db.refresh(unit)
    return unit