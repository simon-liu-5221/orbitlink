"""PR-12 — submitting product feedback against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Feedback, User
from app.main import create_app
from tests.support.auth import bearer, make_user

pytestmark = pytest.mark.integration


@pytest.fixture
def user(db_session: Session) -> User:
    return make_user(db_session)


@pytest.fixture
def api(db_session: Session, user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.rate_limit_feedback] = lambda: None
    with TestClient(app, headers=bearer(user)) as client:
        return client


def test_valid_feedback_is_stored_against_the_caller(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-1."""
    resp = api.post("/api/v1/feedback", json={"rating": 5, "comment": "Love the graph."})
    assert resp.status_code == 201
    body = resp.json()
    assert body["rating"] == 5
    assert body["comment"] == "Love the graph."

    row = db_session.get(Feedback, body["id"])
    assert row is not None and row.user_id == user.id


def test_comment_is_optional(api: TestClient) -> None:
    """AC-2."""
    resp = api.post("/api/v1/feedback", json={"rating": 3})
    assert resp.status_code == 201
    assert resp.json()["comment"] is None


@pytest.mark.parametrize("rating", [0, 6, -1])
def test_rating_out_of_range_is_422(api: TestClient, rating: int) -> None:
    """AC-3."""
    assert api.post("/api/v1/feedback", json={"rating": rating}).status_code == 422


def test_missing_rating_is_422(api: TestClient) -> None:
    """AC-4."""
    assert api.post("/api/v1/feedback", json={"comment": "no rating given"}).status_code == 422


def test_comment_over_length_limit_is_422(api: TestClient) -> None:
    """AC-5."""
    resp = api.post("/api/v1/feedback", json={"rating": 4, "comment": "x" * 2001})
    assert resp.status_code == 422


def test_requires_a_token(db_session: Session) -> None:
    """AC-6."""
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.rate_limit_feedback] = lambda: None
    with TestClient(app) as anon:
        resp = anon.post("/api/v1/feedback", json={"rating": 4})
    assert resp.status_code == 401


def test_the_same_user_can_submit_more_than_once(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-7 — a history, not a single mutable row."""
    first = api.post("/api/v1/feedback", json={"rating": 2, "comment": "meh"})
    second = api.post("/api/v1/feedback", json={"rating": 5, "comment": "actually great"})
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    rows = db_session.scalars(select(Feedback).where(Feedback.user_id == user.id)).all()
    assert len(rows) == 2


def test_rate_limit_refuses_the_eleventh(db_session: Session, user: User) -> None:
    """AC-8 — 10 per hour per IP."""
    from app.jobs.queue import get_redis

    try:
        get_redis().delete("ratelimit:feedback:testclient")
    except Exception:
        pytest.skip("redis unavailable")

    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app, headers=bearer(user)) as client:  # real rate_limit_feedback
        codes = [client.post("/api/v1/feedback", json={"rating": 3}).status_code for _ in range(11)]

    assert codes[:10] == [201] * 10
    assert codes[10] == 429
