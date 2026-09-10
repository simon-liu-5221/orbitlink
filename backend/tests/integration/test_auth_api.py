"""GU-01 (registration) and PR-02 (sign in) against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import REFRESH_COOKIE_NAME
from app.core.config import Settings
from app.db.models import AuthToken, TokenPurpose, User
from app.db.models.user import TRIAL_DAYS
from app.main import create_app
from app.services.email import Message
from tests.support.auth import PASSWORD, bearer, make_user

pytestmark = pytest.mark.integration


class _Outbox:
    """Collects what would have been sent instead of sending it."""

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
    app.dependency_overrides[deps.rate_limit_register] = lambda: None
    app.dependency_overrides[deps.rate_limit_login] = lambda: None
    with TestClient(app) as client:
        return client


def _signup(api: TestClient, **overrides: str) -> httpx.Response:
    suffix = uuid.uuid4().hex[:12]
    body = {
        "email": f"new-{suffix}@example.com",
        "username": f"new_{suffix}",
        "password": PASSWORD,
    }
    body.update(overrides)
    response: httpx.Response = api.post("/api/v1/auth/register", json=body)
    return response


def _token_from_link(outbox: _Outbox) -> str:
    _, _, token = outbox.last.body.partition("?token=")
    return token.split()[0]


# --- GU-01 registration ------------------------------------------------


def test_register_creates_an_unverified_trial_user(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-1, AC-2, AC-9."""
    email = f"ac1-{uuid.uuid4().hex[:8]}@example.com"
    before = datetime.now(UTC)
    resp = _signup(api, email=email)
    assert resp.status_code == 201

    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.email_verified is False
    assert user.subscription_plan == "trial"

    # AC-2: argon2id, and nothing resembling the plaintext
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash

    # AC-9: trial ends 30 days out
    assert user.trial_ends_at is not None
    assert abs(user.trial_ends_at - (before + timedelta(days=TRIAL_DAYS))) < timedelta(minutes=1)

    assert "Confirm your OrbitLink email" in outbox.last.subject


def test_registering_a_known_email_is_indistinguishable(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-3 — same status and body; only the email that lands differs."""
    existing = make_user(db_session)

    fresh = _signup(api)
    repeat = _signup(api, email=existing.email)

    assert fresh.status_code == repeat.status_code == 201
    assert fresh.json() == repeat.json()

    # No second account, and the mail sent back is the "you already have one" note.
    assert db_session.scalars(select(User).where(User.email == existing.email)).all() != []
    assert "already have an OrbitLink account" in outbox.last.subject


def test_weak_password_lists_every_unmet_requirement(api: TestClient) -> None:
    """AC-4 — all problems, not just the first."""
    resp = _signup(api, password="short")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error_code"] == "WEAK_PASSWORD"
    assert len(detail["problems"]) == 2  # too short AND no digit
    assert any("12 characters" in p for p in detail["problems"])
    assert any("digit" in p for p in detail["problems"])


def test_taken_username_is_422(api: TestClient, db_session: Session) -> None:
    existing = make_user(db_session)
    resp = _signup(api, username=existing.username)
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "USERNAME_TAKEN"


def test_invalid_email_is_422(api: TestClient) -> None:
    assert _signup(api, email="not-an-email").status_code == 422


def test_verify_activates_the_account_and_the_token_is_single_use(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-5."""
    email = f"verify-{uuid.uuid4().hex[:8]}@example.com"
    _signup(api, email=email)
    token = _token_from_link(outbox)

    first = api.get("/api/v1/auth/verify", params={"token": token})
    assert first.status_code == 200

    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None and user.email_verified is True

    replay = api.get("/api/v1/auth/verify", params={"token": token})
    assert replay.status_code == 400
    assert replay.json()["detail"]["error_code"] == "TOKEN_INVALID"


def test_expired_verification_token_is_410(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    """AC-6 — a link generated 25 hours ago."""
    _signup(api)
    token = _token_from_link(outbox)
    record = db_session.scalar(
        select(AuthToken).where(AuthToken.purpose == TokenPurpose.EMAIL_VERIFICATION.value)
    )
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.flush()

    resp = api.get("/api/v1/auth/verify", params={"token": token})
    assert resp.status_code == 410
    assert resp.json()["detail"]["error_code"] == "TOKEN_EXPIRED"


def test_unknown_verification_token_is_400(api: TestClient) -> None:
    resp = api.get("/api/v1/auth/verify", params={"token": "nope"})
    assert resp.status_code == 400


def test_resend_verification_is_silent_about_the_address(
    api: TestClient, db_session: Session, outbox: _Outbox
) -> None:
    unverified = make_user(db_session, email_verified=False)
    verified = make_user(db_session, email_verified=True)

    a = api.post("/api/v1/auth/resend-verification", json={"email": unverified.email})
    sent_after_unverified = len(outbox.messages)
    b = api.post("/api/v1/auth/resend-verification", json={"email": verified.email})
    c = api.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"})

    assert a.status_code == b.status_code == c.status_code == 200
    assert a.json() == b.json() == c.json()
    # only the genuinely unverified address gets mail
    assert sent_after_unverified == 1
    assert len(outbox.messages) == 1


def test_register_rate_limit_refuses_the_sixth(db_session: Session, outbox: _Outbox) -> None:
    """AC-8 — 5 per hour per IP."""
    from app.jobs.queue import get_redis

    try:
        get_redis().delete("ratelimit:register:testclient")
    except Exception:
        pytest.skip("redis unavailable")

    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.get_email_backend] = lambda: outbox
    with TestClient(app) as client:  # real rate_limit_register dependency
        codes = [_signup(client).status_code for _ in range(6)]

    assert codes[:5] == [201] * 5
    assert codes[5] == 429


# --- PR-02 sign in -----------------------------------------------------


def test_login_returns_an_access_token_and_sets_the_refresh_cookie(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    resp = api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == user.email

    cookie = resp.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie
    # the raw secret is never what the database holds
    assert db_session.scalar(select(AuthToken).where(AuthToken.token_hash == cookie)) is None

    # and the access token actually opens a door
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == str(user.id)


def test_login_is_case_insensitive_on_email(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    resp = api.post("/api/v1/auth/login", json={"email": user.email.upper(), "password": PASSWORD})
    assert resp.status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    wrong = api.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password-9"}
    )
    unknown = api.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": PASSWORD}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_unverified_account_cannot_sign_in(api: TestClient, db_session: Session) -> None:
    """GU-01 AC-7."""
    user = make_user(db_session, email_verified=False)
    resp = api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "EMAIL_NOT_VERIFIED"


def test_remember_me_extends_the_refresh_cookie(api: TestClient, db_session: Session) -> None:
    settings = Settings(_env_file=None)
    user = make_user(db_session)

    short = api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    long = api.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD, "remember_me": True},
    )

    def max_age(resp: httpx.Response) -> int:
        header = resp.headers["set-cookie"]
        return int(header.split("Max-Age=")[1].split(";")[0])

    assert max_age(short) == settings.refresh_token_days * 86400
    assert max_age(long) == settings.refresh_token_remember_days * 86400


def test_refresh_rotates_the_token_and_the_old_one_dies(
    api: TestClient, db_session: Session
) -> None:
    user = make_user(db_session)
    api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    first_cookie = api.cookies[REFRESH_COOKIE_NAME]

    rotated = api.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["user"]["id"] == str(user.id)
    assert api.cookies[REFRESH_COOKIE_NAME] != first_cookie

    # replaying the spent token is refused
    api.cookies.set(REFRESH_COOKIE_NAME, first_cookie)
    replay = api.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["detail"]["error_code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_without_a_cookie_is_401(api: TestClient) -> None:
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_expired_refresh_token_is_401(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    record = db_session.scalar(
        select(AuthToken).where(
            AuthToken.user_id == user.id,
            AuthToken.purpose == TokenPurpose.REFRESH.value,
        )
    )
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()

    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_logout_revokes_the_session(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    api.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    stale = api.cookies[REFRESH_COOKIE_NAME]

    assert api.post("/api/v1/auth/logout").status_code == 204

    api.cookies.set(REFRESH_COOKIE_NAME, stale)
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_logout_without_a_session_is_still_204(api: TestClient) -> None:
    assert api.post("/api/v1/auth/logout").status_code == 204


def test_me_requires_a_token(api: TestClient, db_session: Session) -> None:
    user = make_user(db_session)
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.get("/api/v1/auth/me", headers=bearer(user)).status_code == 200
