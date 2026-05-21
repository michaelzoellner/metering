from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


# ── Units ────────────────────────────────────────────────────────────────────

class UnitBase(BaseModel):
    name: str

class UnitCreate(UnitBase):
    pass

class UnitUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None

class UnitRead(UnitBase):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Residents ─────────────────────────────────────────────────────────────────

class ResidentBase(BaseModel):
    surname:   str
    givenname: str
    email:     Optional[str] = None

class ResidentCreate(ResidentBase):
    pass

class ResidentUpdate(BaseModel):
    surname:   Optional[str] = None
    givenname: Optional[str] = None
    email:     Optional[str] = None
    active:    Optional[bool] = None

class ResidentRead(ResidentBase):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Residencies ───────────────────────────────────────────────────────────────

class ResidencyBase(BaseModel):
    resident_id: int
    unit_id:     int
    start_date:  datetime
    end_date:    Optional[datetime] = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if v and "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date muss nach start_date liegen")
        return v

class ResidencyCreate(ResidencyBase):
    pass

class ResidencyUpdate(BaseModel):
    end_date: Optional[datetime] = None
    active:   Optional[bool]     = None

class ResidencyRead(ResidencyBase):
    id: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Meters ────────────────────────────────────────────────────────────────────

class MeterBase(BaseModel):
    id:         str             # HA-Sensor-ID
    type_id:    int
    unit_id:    Optional[int] = None
    label:      Optional[str] = None
    start_date: datetime
    end_date:   Optional[datetime] = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v, info):
        if v and "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date muss nach start_date liegen")
        return v

class MeterCreate(MeterBase):
    pass

class MeterUpdate(BaseModel):
    type_id:  Optional[int]      = None
    unit_id:  Optional[int]      = None
    label:    Optional[str]      = None
    end_date: Optional[datetime] = None
    active:   Optional[bool]     = None

class MeterRead(MeterBase):
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── CSV-Import ────────────────────────────────────────────────────────────────

class ImportResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors:  list[str] = []