"""Shared FastAPI dependencies: DB session, current user, rate limiting.

Auth is a **placeholder** for M2 (decision A1): an ``X-User-Id`` header names the
user; absent -> the seeded dev user; present-but-unknown -> 401. Real JWT auth
lands in M3 (spec GU-01).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.models.user import DEV_USER_ID
from app.db.session import SessionLocal
from app.jobs.queue import get_redis

_RATE_LIMIT_PER_MINUTE = 10


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user(
    db: DbSession,
    x_user_id: Annotated[str | None, Header()] = None,
) -> User:
    user_id = DEV_USER_ID
    if x_user_id is not None:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid X-User-Id") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def rate_limit_analyses(request: Request) -> None:
    """Fixed 1-minute window, ``_RATE_LIMIT_PER_MINUTE`` per client IP (SEC-05)."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"ratelimit:analyses:{client_ip}"
    try:
        redis = get_redis()
        count = int(redis.incr(key))
        if count == 1:
            redis.expire(key, 60)
    except Exception:
        return
    if count > _RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"rate limit is {_RATE_LIMIT_PER_MINUTE} analysis requests per minute",
        )
