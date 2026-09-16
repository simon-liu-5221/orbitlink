"""AD-01 (user management) + AD-02 (feedback inbox) against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Feedback, User
from app.main import create_app
from tests.support.auth import PASSWORD, bearer, make_admin, make_user

pytestmark = pytest.mark.integration


@pytest.fixture
def admin(db_session: Session) -> User:
    return make_admin(db_session)


@pytest.fixture
def api(db_session: Session, admin: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app, headers=bearer(admin)) as client:
        return client


# --- AD-01 : list / search --------------------------------------------


def test_admin_sees_every_user_not_just_themselves(
    api: TestClient, db_session: Session, admin: User
) -> None:
    """AC-1."""
    make_user(db_session, username="alice")
    make_user(db_session, username="bob")

    body = api.get("/api/v1/admin/users").json()
    usernames = {row["username"] for row in body}
    assert {"alice", "bob", admin.username}.issubset(usernames)


def test_search_matches_email_or_username(api: TestClient, db_session: Session) -> None:
    """AC-2."""
    make_user(db_session, username="findme", email="findme@example.com")
    make_user(db_session, username="other", email="other@example.com")

    body = api.get("/api/v1/admin/users", params={"q": "findme"}).json()
    assert [row["username"] for row in body] == ["findme"]


def test_a_regular_user_gets_403_on_every_admin_endpoint(
    db_session: Session,
) -> None:
    """AC-3."""
    user = make_user(db_session)
    target = make_user(db_session)
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app, headers=bearer(user)) as client:
        assert client.get("/api/v1/admin/users").status_code == 403
        assert client.get("/api/v1/admin/feedback").status_code == 403
        assert client.post(f"/api/v1/admin/users/{target.id}/suspend").status_code == 403


def test_unauthenticated_gets_401(db_session: Session) -> None:
    """AC-4."""
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app) as anon:
        assert anon.get("/api/v1/admin/users").status_code == 401


# --- AD-01 : suspend / unsuspend ---------------------------------------


def test_suspending_a_user_sets_suspended_at(api: TestClient, db_session: Session) -> None:
    """AC-5."""
    target = make_user(db_session)
    resp = api.post(f"/api/v1/admin/users/{target.id}/suspend")
    assert resp.status_code == 200
    assert resp.json()["suspended_at"] is not None


def test_suspended_account_cannot_log_in(api: TestClient, db_session: Session) -> None:
    """AC-6."""
    target = make_user(db_session)
    api.post(f"/api/v1/admin/users/{target.id}/suspend")

    plain_app = create_app()
    plain_app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(plain_app) as client:
        resp = client.post("/api/v1/auth/login", json={"email": target.email, "password": PASSWORD})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "ACCOUNT_SUSPENDED"


def test_an_already_issued_token_dies_immediately_on_suspension(
    api: TestClient, db_session: Session
) -> None:
    """AC-7 — no waiting for the access token to expire."""
    target = make_user(db_session)
    target_headers = bearer(target)

    plain_app = create_app()
    plain_app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(plain_app, headers=target_headers) as target_client:
        assert target_client.get("/api/v1/projects").status_code == 200

        api.post(f"/api/v1/admin/users/{target.id}/suspend")

        resp = target_client.get("/api/v1/projects")
    assert resp.status_code == 403
    assert resp.json()["detail"]["error_code"] == "ACCOUNT_SUSPENDED"


def test_admin_cannot_suspend_themselves(api: TestClient, admin: User) -> None:
    """AC-8."""
    resp = api.post(f"/api/v1/admin/users/{admin.id}/suspend")
    assert resp.status_code == 409


def test_admin_cannot_suspend_another_admin(api: TestClient, db_session: Session) -> None:
    """AC-9."""
    other_admin = make_admin(db_session)
    resp = api.post(f"/api/v1/admin/users/{other_admin.id}/suspend")
    assert resp.status_code == 409


def test_unsuspend_restores_the_account(api: TestClient, db_session: Session) -> None:
    """AC-10."""
    target = make_user(db_session, suspended_at=datetime.now(UTC))
    resp = api.post(f"/api/v1/admin/users/{target.id}/unsuspend")
    assert resp.status_code == 200
    assert resp.json()["suspended_at"] is None

    plain_app = create_app()
    plain_app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(plain_app) as client:
        login = client.post(
            "/api/v1/auth/login", json={"email": target.email, "password": PASSWORD}
        )
    assert login.status_code == 200


def test_suspend_and_unsuspend_are_idempotent(api: TestClient, db_session: Session) -> None:
    """AC-11."""
    target = make_user(db_session)
    assert api.post(f"/api/v1/admin/users/{target.id}/suspend").status_code == 200
    assert api.post(f"/api/v1/admin/users/{target.id}/suspend").status_code == 200
    assert api.post(f"/api/v1/admin/users/{target.id}/unsuspend").status_code == 200
    assert api.post(f"/api/v1/admin/users/{target.id}/unsuspend").status_code == 200


def test_suspending_a_missing_user_is_404(api: TestClient) -> None:
    assert api.post(f"/api/v1/admin/users/{uuid.uuid4()}/suspend").status_code == 404


# --- AD-02 : feedback inbox ---------------------------------------------


def test_feedback_inbox_includes_the_submitters_identity(
    api: TestClient, db_session: Session
) -> None:
    """AC-1 (AD-02)."""
    someone = make_user(db_session, username="feedback-giver")
    db_session.add(Feedback(user_id=someone.id, rating=4, comment="pretty good"))
    db_session.flush()

    body = api.get("/api/v1/admin/feedback").json()
    row = next(r for r in body if r["username"] == "feedback-giver")
    assert row["rating"] == 4
    assert row["comment"] == "pretty good"
    assert row["user_email"] == someone.email


def test_feedback_inbox_is_newest_first(api: TestClient, db_session: Session) -> None:
    """AC-2 (AD-02)."""
    user = make_user(db_session)
    older = Feedback(user_id=user.id, rating=1, created_at=datetime.now(UTC) - timedelta(hours=1))
    newer = Feedback(user_id=user.id, rating=5, created_at=datetime.now(UTC))
    db_session.add_all([older, newer])
    db_session.flush()

    body = api.get("/api/v1/admin/feedback").json()
    ids = [r["id"] for r in body]
    assert ids.index(str(newer.id)) < ids.index(str(older.id))


def test_feedback_inbox_forbidden_for_non_admin(db_session: Session) -> None:
    """AC-3 (AD-02)."""
    user = make_user(db_session)
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app, headers=bearer(user)) as client:
        assert client.get("/api/v1/admin/feedback").status_code == 403


def test_feedback_inbox_requires_a_token(db_session: Session) -> None:
    """AC-4 (AD-02)."""
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app) as anon:
        assert anon.get("/api/v1/admin/feedback").status_code == 401


def test_empty_feedback_inbox_is_an_empty_list(api: TestClient) -> None:
    """AC-5 (AD-02)."""
    assert api.get("/api/v1/admin/feedback").json() == []
