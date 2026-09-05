"""ORM model registry.

Import every model module here so that ``Base.metadata`` is fully populated
before Alembic autogenerate or ``create_all`` runs.

M0 has no domain tables yet — the job state machine (``analysis_jobs``) arrives
in M2 (ADR-0002), auth tables in M3. Add imports here as models land.
"""

from app.db.base import Base

__all__ = ["Base"]
