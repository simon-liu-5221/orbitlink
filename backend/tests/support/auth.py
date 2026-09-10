"""Test helpers for building real accounts and signed-in clients (M3).

M2's tests leaned on a dev placeholder user seeded by the migration. That is
gone — every test that needs an actor now makes one here.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.models.user import TRIAL_DAYS

#: Meets the GU-01 policy (12+ chars, a digit, a letter).
PASSWORD = "correct-horse-7"

#: Hashed once per test session rather than once per user — argon2id is
#: deliberately slow, and every account here shares the same password.
PASSWORD_HASH = hash_password(PASSWORD)


def make_user(
    db: Session,
    *,
    email: str | None = None,
    username: str | None = None,
    password_hash: str = PASSWORD_HASH,
    email_verified: bool = True,
) -> User:
    """Insert a usable account. Defaults to verified, since most tests want one."""
    suffix = uuid.uuid4().hex[:12]
    user = User(
        email=email or f"user-{suffix}@example.com",
        username=username or f"user_{suffix}",
        password_hash=password_hash,
        email_verified=email_verified,
        subscription_plan="trial",
        trial_ends_at=datetime.now(UTC) + timedelta(days=TRIAL_DAYS),
    )
    db.add(user)
    db.flush()
    return user


def bearer(user: User, settings: Settings | None = None) -> dict[str, str]:
    """An ``Authorization`` header carrying a valid access token for ``user``."""
    settings = settings or get_settings()
    token = create_access_token(
        str(user.id), secret=settings.jwt_secret, expires_in=timedelta(minutes=15)
    )
    return {"Authorization": f"Bearer {token}"}
