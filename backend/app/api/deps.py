"""Shared FastAPI dependencies: DB session, current user, rate limiting.

Auth is a bearer access token (JWT) in ``Authorization`` — see specs GU-01 /
PR-02. The M2 ``X-User-Id`` placeholder is gone.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.models import User
from app.db.session import SessionLocal
from app.jobs.queue import get_redis
from app.services.email import EmailBackend, build_email_backend

_UNAUTHORISED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_email_backend(settings: AppSettings) -> EmailBackend:
    return build_email_backend(settings)


Email = Annotated[EmailBackend, Depends(get_email_backend)]


def current_user(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _UNAUTHORISED
    try:
        subject = decode_access_token(credentials.credentials, secret=settings.jwt_secret)
        user_id = uuid.UUID(subject)
    except (InvalidAccessTokenError, ValueError) as exc:
        raise _UNAUTHORISED from exc

    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTHORISED
    return user


CurrentUser = Annotated[User, Depends(current_user)]


# --- refresh cookie ---------------------------------------------------

#: The refresh token never reaches JavaScript (decision B1). The path scopes it
#: to the auth router, so it is not sent with every other API call.
REFRESH_COOKIE_NAME = "orbitlink_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]


# --- rate limiting ----------------------------------------------------


def rate_limiter(bucket: str, *, limit: int, window_seconds: int) -> Callable[[Request], None]:
    """Fixed-window limiter keyed on client IP, backed by redis (SEC-05).

    If redis is unreachable the limiter opens rather than taking the API down
    with it.
    """

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{bucket}:{client_ip}"
        try:
            redis = get_redis()
            count = int(redis.incr(key))
            if count == 1:
                redis.expire(key, window_seconds)
        except Exception:
            return
        if count > limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"rate limit is {limit} requests per {window_seconds}s",
            )

    return dependency


#: 10 analysis starts per minute per IP (PR-01 AC-10, SEC-05).
rate_limit_analyses = rate_limiter("analyses", limit=10, window_seconds=60)
#: 5 registrations per hour per IP; the 6th is refused (GU-01 AC-8).
rate_limit_register = rate_limiter("register", limit=5, window_seconds=3600)
#: Sign-in attempts, to slow credential stuffing.
rate_limit_login = rate_limiter("login", limit=10, window_seconds=60)
