"""User model (spec GU-01).

Passwords are argon2id hashes; nothing here stores a secret in the clear.
Accounts start unverified on a 30-day trial.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.auth_token import AuthToken
    from app.db.models.feedback import Feedback
    from app.db.models.project import Project

TRIAL_DAYS = 30

#: "admin" unlocks the admin API (AD-01/AD-02); everyone starts as "user".
#: Nothing here can self-promote — becoming an admin is a manual DB update or
#: scripts/promote_admin.py, deliberately outside the app's own UI.
DEFAULT_ROLE = "user"
ADMIN_ROLE = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    subscription_plan: Mapped[str] = mapped_column(String(20), default="trial")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    role: Mapped[str] = mapped_column(String(20), default=DEFAULT_ROLE)
    #: Set by an admin (AD-01). A suspended account can't log in, and an
    #: already-issued access token stops working on its very next request.
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN_ROLE

    @property
    def is_suspended(self) -> bool:
        return self.suspended_at is not None

    projects: Mapped[list[Project]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    auth_tokens: Mapped[list[AuthToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
