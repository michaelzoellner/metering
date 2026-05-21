from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # erkennt abgebrochene Verbindungen
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI-Dependency: liefert eine DB-Session und schließt sie am Ende."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()