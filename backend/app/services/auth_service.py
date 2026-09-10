"""Registration, sign-in, token rotation (specs GU-01 / PR-02).

Two things here are deliberate and easy to get wrong:

1. **Registration never reveals whether an email is already taken.** Both paths
   do one argon2 hash and send one email, so the status code, body and response
   time are indistinguishable (GU-01 AC-3).
2. **Refresh tokens rotate.** Using one marks it spent and issues a new one, so
   a stolen token is good for at most one use before the real user's next
   refresh invalidates the thief (or vice versa, which surfaces the theft).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.db.models import AuthToken, TokenPurpose, User
from app.db.models.user import TRIAL_DAYS
from app.services.email import (
    EmailBackend,
    already_registered_message,
    verification_message,
)

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    pass


class WeakPasswordError(AuthError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("password does not meet the requirements")
        self.problems = problems


class UsernameTakenError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class EmailNotVerifiedError(AuthError):
    pass


class InvalidTokenError(AuthError):
    pass


class ExpiredTokenError(AuthError):
    pass


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    #: Seconds until the access token expires.
    expires_in: int
    refresh_token: str
    #: Seconds until the refresh token expires — straight into the cookie's Max-Age.
    refresh_expires_in: int


# --- registration -----------------------------------------------------


def register(
    db: Session,
    *,
    email: str,
    username: str,
    password: str,
    settings: Settings,
    email_backend: EmailBackend,
) -> None:
    """Always succeeds from the caller's point of view (GU-01 AC-1 / AC-3)."""
    problems = security.password_policy_errors(password)
    if problems:
        raise WeakPasswordError(problems)

    normalised_email = email.strip().lower()
    normalised_username = username.strip()

    if db.scalar(select(User).where(User.username == normalised_username).limit(1)):
        raise UsernameTakenError(f"username {normalised_username!r} is taken")

    existing = db.scalar(select(User).where(User.email == normalised_email).limit(1))
    if existing is not None:
        # Burn the same CPU a real signup would, then send a different email.
        security.burn_password_time()
        email_backend.send(already_registered_message(to=normalised_email))
        return

    now = datetime.now(UTC)
    user = User(
        email=normalised_email,
        username=normalised_username,
        password_hash=security.hash_password(password),
        email_verified=False,
        subscription_plan="trial",
        trial_ends_at=now + timedelta(days=TRIAL_DAYS),
    )
    db.add(user)
    db.flush()

    token = _issue_token(
        db,
        user,
        TokenPurpose.EMAIL_VERIFICATION,
        timedelta(hours=settings.email_verification_hours),
    )
    email_backend.send(
        verification_message(
            to=user.email,
            username=user.username,
            link=f"{settings.frontend_base_url.rstrip('/')}/verify?token={token}",
            hours=settings.email_verification_hours,
        )
    )


def verify_email(db: Session, *, token: str) -> User:
    record = _consume_token(db, token, TokenPurpose.EMAIL_VERIFICATION)
    user = record.user
    user.email_verified = True
    db.flush()
    return user


def resend_verification(
    db: Session, *, email: str, settings: Settings, email_backend: EmailBackend
) -> None:
    """Silent about whether the address exists or is already verified."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()).limit(1))
    if user is None or user.email_verified:
        return
    token = _issue_token(
        db,
        user,
        TokenPurpose.EMAIL_VERIFICATION,
        timedelta(hours=settings.email_verification_hours),
    )
    email_backend.send(
        verification_message(
            to=user.email,
            username=user.username,
            link=f"{settings.frontend_base_url.rstrip('/')}/verify?token={token}",
            hours=settings.email_verification_hours,
        )
    )


# --- sign in ----------------------------------------------------------


def login(
    db: Session,
    *,
    email: str,
    password: str,
    remember: bool,
    settings: Settings,
) -> tuple[User, IssuedTokens]:
    user = db.scalar(select(User).where(User.email == email.strip().lower()).limit(1))
    if user is None:
        security.burn_password_time()
        raise InvalidCredentialsError("email or password is wrong")
    if not security.verify_password(password, user.password_hash):
        raise InvalidCredentialsError("email or password is wrong")
    if not user.email_verified:
        raise EmailNotVerifiedError("confirm your email address before signing in")

    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)

    return user, _issue_session(db, user, remember=remember, settings=settings)


def refresh_session(
    db: Session, *, refresh_token: str, settings: Settings
) -> tuple[User, IssuedTokens]:
    record = _consume_token(db, refresh_token, TokenPurpose.REFRESH)
    remaining = record.expires_at - datetime.now(UTC)
    remember = remaining > timedelta(days=settings.refresh_token_days)
    return record.user, _issue_session(db, record.user, remember=remember, settings=settings)


def logout(db: Session, *, refresh_token: str | None) -> None:
    """Revoke the refresh token. Silently fine if it was already gone."""
    if not refresh_token:
        return
    record = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == security.hash_token(refresh_token),
            AuthToken.purpose == TokenPurpose.REFRESH.value,
        )
    )
    if record is not None and record.used_at is None:
        record.used_at = datetime.now(UTC)
        db.flush()


def revoke_all_sessions(db: Session, user_id: uuid.UUID) -> None:
    """Used after a password change (PR-03) — every device signs out."""
    now = datetime.now(UTC)
    for record in db.scalars(
        select(AuthToken).where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == TokenPurpose.REFRESH.value,
            AuthToken.used_at.is_(None),
        )
    ):
        record.used_at = now
    db.flush()


# --- internals --------------------------------------------------------


def _issue_session(db: Session, user: User, *, remember: bool, settings: Settings) -> IssuedTokens:
    access_ttl = timedelta(minutes=settings.access_token_minutes)
    refresh_days = settings.refresh_token_remember_days if remember else settings.refresh_token_days
    refresh_ttl = timedelta(days=refresh_days)

    access_token = security.create_access_token(
        str(user.id), secret=settings.jwt_secret, expires_in=access_ttl
    )
    refresh_token = _issue_token(db, user, TokenPurpose.REFRESH, refresh_ttl)
    return IssuedTokens(
        access_token=access_token,
        expires_in=int(access_ttl.total_seconds()),
        refresh_token=refresh_token,
        refresh_expires_in=int(refresh_ttl.total_seconds()),
    )


def _issue_token(db: Session, user: User, purpose: TokenPurpose, ttl: timedelta) -> str:
    raw = security.generate_token()
    db.add(
        AuthToken(
            user_id=user.id,
            token_hash=security.hash_token(raw),
            purpose=purpose.value,
            expires_at=datetime.now(UTC) + ttl,
        )
    )
    db.flush()
    return raw


def _consume_token(db: Session, raw: str, purpose: TokenPurpose) -> AuthToken:
    record = db.scalar(
        select(AuthToken).where(
            AuthToken.token_hash == security.hash_token(raw),
            AuthToken.purpose == purpose.value,
        )
    )
    if record is None or record.used_at is not None:
        raise InvalidTokenError("token is not valid")
    if record.expires_at <= datetime.now(UTC):
        raise ExpiredTokenError("token has expired")
    record.used_at = datetime.now(UTC)
    db.flush()
    return record
