from datetime import datetime
from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, Text,
    TIMESTAMP, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class Unit(Base):
    __tablename__ = "units"

    id         = Column(Integer, primary_key=True)
    name       = Column(Text, nullable=False, unique=True)
    active     = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    meters      = relationship("Meter",     back_populates="unit")
    residencies = relationship("Residency", back_populates="unit")


class Resident(Base):
    __tablename__ = "residents"

    id         = Column(Integer, primary_key=True)
    surname    = Column(Text, nullable=False)
    givenname  = Column(Text, nullable=False)
    email      = Column(Text)
    active     = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    residencies = relationship("Residency", back_populates="resident")


class Residency(Base):
    __tablename__ = "residencies"

    id          = Column(Integer, primary_key=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    unit_id     = Column(Integer, ForeignKey("units.id"),     nullable=False)
    start_date  = Column(TIMESTAMP(timezone=True), nullable=False)
    end_date    = Column(TIMESTAMP(timezone=True))
    active      = Column(Boolean, nullable=False, default=True)
    created_at  = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at  = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    unit     = relationship("Unit",     back_populates="residencies")
    resident = relationship("Resident", back_populates="residencies")


class MeterType(Base):
    __tablename__ = "meter_types"

    id   = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)

    meters = relationship("Meter", back_populates="meter_type")


class Meter(Base):
    __tablename__ = "meters"

    id         = Column(Text, primary_key=True)   # HA-Sensor-ID
    type_id    = Column(Integer, ForeignKey("meter_types.id"), nullable=False)
    unit_id    = Column(Integer, ForeignKey("units.id"))       # nullable!
    label      = Column(Text)
    start_date = Column(TIMESTAMP(timezone=True), nullable=False)
    end_date   = Column(TIMESTAMP(timezone=True))
    active     = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    unit       = relationship("Unit",      back_populates="meters")
    meter_type = relationship("MeterType", back_populates="meters")