"""Database engine and session management."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

# prepare_threshold=None disables psycopg's server-side prepared statements.
# Required when the connection goes through a transaction-mode pooler
# (Neon's -pooler endpoint, PgBouncer); harmless otherwise.
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
