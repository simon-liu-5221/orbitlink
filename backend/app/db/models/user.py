"""User model — minimal for M2 (dev-placeholder auth).

M3 (spec GU-01) adds ``password_hash``, ``email_verified``,
``subscription_plan``, ``trial_ends_at`` via a follow-up migration.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.project import Project

#: The seeded stand-in user until real auth lands (M3, decision A1).
DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEV_USER_EMAIL = "dev@orbitlink.local"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)

    projects: Mapped[list[Project]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
