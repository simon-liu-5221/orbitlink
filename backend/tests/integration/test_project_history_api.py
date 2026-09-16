"""AN-06 (phase 1) — GET /projects/{id}/analyses against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Analysis, AnalysisJob, Project, User
from app.jobs.state_machine import JobStatus
from app.main import create_app
from tests.support.auth import bearer, make_user

pytestmark = pytest.mark.integration

_JOB_PARAMS = {
    "target_kind": "video",
    "target_value": "v",
    "max_comments": 1,
    "channel_video_count": 1,
}


@pytest.fixture
def user(db_session: Session) -> User:
    return make_user(db_session)


@pytest.fixture
def api(db_session: Session, user: User) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app, headers=bearer(user)) as client:
        return client


def _project(db: Session, owner: User) -> Project:
    project = Project(name="P", user_id=owner.id)
    db.add(project)
    db.flush()
    return project


def _analysis(
    db: Session, project: Project, *, created_at: datetime, **overrides: object
) -> Analysis:
    job = AnalysisJob(
        project=project, source_url="u", status=JobStatus.COMPLETED.value, params=_JOB_PARAMS
    )
    db.add(job)
    db.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id, created_at=created_at, **overrides)
    db.add(analysis)
    db.flush()
    return analysis


def test_returned_oldest_first(api: TestClient, db_session: Session, user: User) -> None:
    """AC-1."""
    project = _project(db_session, user)
    base = datetime.now(UTC) - timedelta(days=10)
    a1 = _analysis(db_session, project, created_at=base, node_count=10)
    a2 = _analysis(db_session, project, created_at=base + timedelta(days=5), node_count=20)
    a3 = _analysis(db_session, project, created_at=base + timedelta(days=9), node_count=30)

    body = api.get(f"/api/v1/projects/{project.id}/analyses").json()
    assert [row["id"] for row in body] == [str(a1.id), str(a2.id), str(a3.id)]


def test_sentiment_index_from_distribution(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-2 — (positive% - negative%) / 100, no extra queries against comments/nodes."""
    project = _project(db_session, user)
    _analysis(
        db_session,
        project,
        created_at=datetime.now(UTC),
        sentiment_summary={"distribution": {"positive": 70.0, "neutral": 10.0, "negative": 20.0}},
    )

    body = api.get(f"/api/v1/projects/{project.id}/analyses").json()
    assert body[0]["sentiment_index"] == pytest.approx(0.5)


def test_missing_or_malformed_distribution_is_null_not_a_crash(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    _analysis(db_session, project, created_at=datetime.now(UTC), sentiment_summary={})
    _analysis(
        db_session,
        project,
        created_at=datetime.now(UTC) + timedelta(minutes=1),
        sentiment_summary={"distribution": "not a dict"},
    )

    body = api.get(f"/api/v1/projects/{project.id}/analyses").json()
    assert body[0]["sentiment_index"] is None
    assert body[1]["sentiment_index"] is None


def test_missing_and_other_users_project_answer_identically(
    api: TestClient, db_session: Session
) -> None:
    """AC-3."""
    someone_else = make_user(db_session)
    theirs = _project(db_session, someone_else)

    not_yours = api.get(f"/api/v1/projects/{theirs.id}/analyses")
    missing = api.get(f"/api/v1/projects/{uuid.uuid4()}/analyses")
    assert not_yours.status_code == missing.status_code == 403
    assert not_yours.json() == missing.json()


def test_requires_a_token(db_session: Session, user: User) -> None:
    """AC-4."""
    project = _project(db_session, user)
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/projects/{project.id}/analyses").status_code == 401


def test_a_project_with_no_analyses_yet_is_an_empty_list(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-5."""
    project = _project(db_session, user)
    assert api.get(f"/api/v1/projects/{project.id}/analyses").json() == []


def test_insufficient_data_flag_is_passed_through(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    _analysis(db_session, project, created_at=datetime.now(UTC), insufficient_data=True)

    body = api.get(f"/api/v1/projects/{project.id}/analyses").json()
    assert body[0]["insufficient_data"] is True
