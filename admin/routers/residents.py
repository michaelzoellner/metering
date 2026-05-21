from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

router = APIRouter(prefix="/residents", tags=["residents"])


@router.get("/", response_model=list[schemas.ResidentRead])
def list_residents(include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(models.Resident)
    if not include_inactive:
        q = q.filter(models.Resident.active == True)
    return q.order_by(models.Resident.surname, models.Resident.givenname).all()


@router.get("/{resident_id}", response_model=schemas.ResidentRead)
def get_resident(resident_id: int, db: Session = Depends(get_db)):
    r = db.get(models.Resident, resident_id)
    if not r:
        raise HTTPException(404, "Resident nicht gefunden")
    return r


@router.post("/", response_model=schemas.ResidentRead, status_code=201)
def create_resident(body: schemas.ResidentCreate, db: Session = Depends(get_db)):
    r = models.Resident(**body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.patch("/{resident_id}", response_model=schemas.ResidentRead)
def update_resident(resident_id: int, body: schemas.ResidentUpdate, db: Session = Depends(get_db)):
    r = db.get(models.Resident, resident_id)
    if not r:
        raise HTTPException(404, "Resident nicht gefunden")

    if body.active is False:
        # Prüfen ob noch aktive Mietverhältnisse laufen
        open_res = (
            db.query(models.Residency)
            .filter(models.Residency.resident_id == resident_id,
                    models.Residency.active == True,
                    models.Residency.end_date == None)
            .first()
        )
        if open_res:
            raise HTTPException(
                400,
                "Mieter kann nicht deaktiviert werden: offenes Mietverhältnis vorhanden."
            )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return r