"""PR-03 — password reset against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import REFRESH_COOKIE_NAME
from app.core import security
from app.db.models import AuthToken, TokenPurpose, User
from app.main import create_app
from app.services.email import Message
from tests.support.auth import PASSWORD, make_user

pytestmark = pytest.mark.integration

#: A distinct password that also satisfies the GU-01 policy.
NEW_PASSWORD = "brand-new-pw-42"


class _Outbox:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def send(self, message: Message) -> None:
        self.messages.append(message)

    @property
    def last(self) -> Message:
        assert self.messages, "expected an email to have been sent"
        return self.messages[-1]


@pytest.fixture
def outbox() -> _Outbox:
    return _Outbox()


@pytest.fixture
def api(db_session: Session, outbox: _Outbox) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_email_backend] = lambda: outbox
    app.dependency_overrides[deps.rate_limit_forgot_password] = lambda: None
    app.dependency_overrides[deps.rate_limit_login] = lambda: None
    with TestClient(app) as client:
        return client


def _reset_token(outbox: _Outbox) -> str:
    _, _, token = outbox.last.body.partition("?token=")
    return token.split()[0]


def _forgot(api: TestClient, email: str) -> httpx.Response:
    return api.post("/api/v1/auth/forgot-password", json={"email": email})


def _reset(api: TestClient, token: str, password: str = NEW_PASSWORD) -> httpx.Response:
    return api.post("/api/v1/auth/reset-password", json={"token": token, "password": password})


# --- AC-1 / AC-2 : request a link ------------------------------------


def test_forgot_password_issues_a_hashed_single_use_token(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-1."""
    user = make_user(db_session)
    resp = _forgot(api, user.email)
    assert resp.status_code == 200

    record = db_session.scalar(
        select(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == TokenPurpose.PASSWORD_RESET.value,
        )
    )
    assert record is not None
    assert record.used_at is None
    # only a digest is stored, never the raw secret from the link
    raw = _reset_token(outbox)
    assert record.token_hash == security.hash_token(raw)
    assert record.token_hash != raw
    assert "reset" in outbox.last.subject.lower()


def test_forgot_password_is_silent_about_unknown_addresses(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-2 — same status and body, and no email, for an address with no account."""
    user = make_user(db_session)
    known = _forgot(api, user.email)
    sent_after_known = len(outbox.messages)
    unknown = _forgot(api, "nobody@example.com")

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert sent_after_known == 1
    assert len(outbox.messages) == 1  # the unknown address added nothing


# --- AC-3 / AC-5 / AC-6 : perform the reset -------------------------


def test_reset_password_changes_the_hash_and_burns_the_token(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-3."""
    user = make_user(db_session)
    old_hash = user.password_hash
    _forgot(api, user.email)
    token = _reset_token(outbox)

    resp = _reset(api, token)
    assert resp.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.password_hash != old_hash
    assert refreshed.password_hash.startswith("$argon2id$")
    assert security.verify_password(NEW_PASSWORD, refreshed.password_hash)

    # the token cannot be replayed
    replay = _reset(api, token)
    assert replay.status_code == 400
    assert replay.json()["detail"]["error_code"] == "TOKEN_INVALID"


def test_unknown_reset_token_is_400(api: TestClient) -> None:
    """AC-5."""
    resp = _reset(api, "not-a-real-token")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "TOKEN_INVALID"


def test_weak_new_password_lists_every_problem(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-6."""
    user = make_user(db_session)
    _forgot(api, user.email)
    token = _reset_token(outbox)

    resp = _reset(api, token, password="short")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_code"] == "WEAK_PASSWORD"
    assert len(detail["problems"]) == 2
    assert any("12 characters" in p for p in detail["problems"])
    assert any("digit" in p for p in detail["problems"])

    # a rejected weak password must NOT have consumed the token
    good = _reset(api, token)
    assert good.status_code == 200


# --- AC-4 : expiry -------------------------------------------------


def test_expired_reset_token_is_410(api: TestClient, db_session: Session, outbox: _Outbox) -> None:
    """AC-4."""
    user = make_user(db_session)
    _forgot(api, user.email)
    token = _reset_token(outbox)
    record = db_session.scalar(
        select(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == TokenPurpose.PASSWORD_RESET.value,
        )
    )
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.flush()

    resp = _reset(api, token)
    assert resp.status_code == 410
    assert resp.json()["detail"]["error_code"] == "TOKEN_EXPIRED"


# --- AC-7 / AC-8 : consequences of a successful reset -------------


def test_old_password_stops_working_new_one_starts(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-7."""
    user = make_user(db_session)
    _forgot(api, user.email)
    _reset(api, _reset_token(outbox))

    old = api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    new = api.post("/api/v1/auth/login", json={"email": user.email, "password": NEW_PASSWORD})
    assert old.status_code == 401
    assert new.status_code == 200


def test_reset_revokes_every_existing_session(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-8."""
    user = make_user(db_session)
    api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    stale_cookie = api.cookies[REFRESH_COOKIE_NAME]

    _forgot(api, user.email)
    _reset(api, _reset_token(outbox))

    api.cookies.set(REFRESH_COOKIE_NAME, stale_cookie)
    assert api.post("/api/v1/auth/refresh").status_code == 401


# --- AC-9 : re-requesting supersedes the old link ----------------


def test_requesting_a_second_link_invalidates_the_first(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-9."""
    user = make_user(db_session)
    _forgot(api, user.email)
    first_token = _reset_token(outbox)
    _forgot(api, user.email)
    second_token = _reset_token(outbox)
    assert first_token != second_token

    assert _reset(api, first_token).status_code == 400
    assert _reset(api, second_token).status_code == 200


# --- AC-10 : an unverified account gets verified -----------------


def test_reset_verifies_an_unverified_account(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-10 — clicking the emailed link is proof of inbox control."""
    user = make_user(db_session, email_verified=False)
    _forgot(api, user.email)
    resp = _reset(api, _reset_token(outbox))
    assert resp.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None and refreshed.email_verified is True

    login = api.post("/api/v1/auth/login", json={"email": user.email, "password": NEW_PASSWORD})
    assert login.status_code == 200


# --- AC-11 : rate limit -----------------------------------------


def test_forgot_password_rate_limit_refuses_the_sixth(db_session: Session, outbox: _Outbox) -> None:
    """AC-11 — 5 per hour per IP."""
    from app.jobs.queue import get_redis

    try:
        get_redis().delete("ratelimit:forgot_password:testclient")
    except Exception:
        pytest.skip("redis unavailable")

    user = make_user(db_session)
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_email_backend] = lambda: outbox
    with TestClient(app) as client:  # the real rate_limit_forgot_password dependency
        codes = [
            client.post("/api/v1/auth/forgot-password", json={"email": user.email}).status_code
            for _ in range(6)
        ]

    assert codes[:5] == [200] * 5
    assert codes[5] == 429
