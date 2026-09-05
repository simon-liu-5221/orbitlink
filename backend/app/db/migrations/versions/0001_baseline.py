"""baseline — establish the alembic version table

No domain tables yet. This revision exists so every environment shares a known
migration baseline; M2 adds ``analysis_jobs`` (ADR-0002) on top of it.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-06
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
