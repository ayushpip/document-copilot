"""SQLAlchemy session construction for request-scoped database access."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def get_database_url() -> str:
    if settings.database_url.startswith("postgresql://"):
        return settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return settings.database_url


engine = create_engine(get_database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["SessionLocal", "engine", "get_session"]
