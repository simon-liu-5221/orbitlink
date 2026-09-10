"""``auth_tokens`` — hashed, expiring, single-use-or-revocable secrets.

One table covers three purposes because they are the same shape: an opaque
random secret handed to the user once, stored only as a SHA-256 digest, with an
expiry and a "spent" marker.

* ``email_verification`` — consumed by clicking the link (GU-01)
* ``password_reset`` — consumed once (PR-03)
* ``refresh`` — rotated on every use, revoked on logout (PR-02)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class TokenPurpose(enum.StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
    REFRESH = "refresh"


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: SHA-256 hex of the secret. The secret itself is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(32), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    #: Set when the token is consumed (one-shot) or revoked (logout).
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def purpose_enum(self) -> TokenPurpose:
        return TokenPurpose(self.purpose)

    user: Mapped[User] = relationship(back_populates="auth_tokens")
