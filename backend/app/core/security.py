"""Password hashing, opaque tokens, and access JWTs (M3, specs GU-01 / PR-02).

Two token kinds, deliberately different:

* **access token** — a short-lived HS256 JWT. Stateless, verified without a DB
  hit, carries only the user id.
* **refresh / email / reset tokens** — opaque random strings. Only their SHA-256
  digest is stored (``auth_tokens``), so a database leak does not hand over
  live sessions, and they can be revoked or consumed exactly once.

ADR-0001 says "self-built JWT (access + refresh)"; the refresh half is opaque
rather than a JWT precisely so it can be revoked — see spec PR-02.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_JWT_ALGORITHM = "HS256"
_ACCESS_TOKEN_TYPE = "access"

#: Argon2id with library defaults (OWASP-acceptable: 64 MiB, t=3, p=4).
_hasher = PasswordHasher()

#: A pre-computed hash used to burn the same CPU time when an account does not
#: exist, so response timing does not leak account existence (GU-01 AC-3).
_DUMMY_HASH = _hasher.hash("orbitlink-timing-equaliser")


# --- passwords --------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return True


def burn_password_time() -> None:
    """Spend a password-verification's worth of CPU on a throwaway hash."""
    verify_password("orbitlink-timing-equaliser", _DUMMY_HASH)


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# --- password policy -------------------------------------------------

#: NIST SP 800-63B: length is what matters; no special-character theatre.
MIN_PASSWORD_LENGTH = 12


def password_policy_errors(password: str) -> list[str]:
    """Every unmet requirement, not just the first (GU-01 AC-4)."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if not any(character.isdigit() for character in password):
        problems.append("must contain at least one digit")
    if not any(character.isalpha() for character in password):
        problems.append("must contain at least one letter")
    return problems


# --- opaque tokens ---------------------------------------------------


def generate_token(nbytes: int = 32) -> str:
    """A URL-safe secret. Returned to the user once; never stored in the clear."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 hex digest — what actually goes in the database.

    Deliberately not Argon2: these are 256-bit random secrets, not
    human-chosen passwords, so there is nothing to brute-force and lookups
    need to be a fast indexed equality check.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- access JWT -------------------------------------------------------


class InvalidAccessTokenError(ValueError):
    pass


def create_access_token(user_id: str, *, secret: str, expires_in: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": _ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> str:
    """Return the subject (user id), or raise :class:`InvalidAccessTokenError`."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError(str(exc)) from exc
    if payload.get("type") != _ACCESS_TOKEN_TYPE:
        raise InvalidAccessTokenError("not an access token")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidAccessTokenError("missing subject")
    return subject
