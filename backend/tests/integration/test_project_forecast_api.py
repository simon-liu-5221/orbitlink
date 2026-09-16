"""AN-06 (phase 2) — GET /projects/{id}/analyses/forecast against a real
database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analysis.forecast import MIN_HISTORY_POINTS
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


def _seed(db: Session, project: Project, count: int, **overrides: object) -> None:
    base = datetime.now(UTC) - timedelta(days=count)
    for i in range(count):
        _analysis(
            db,
            project,
            created_at=base + timedelta(days=i),
            node_count=10 + i,
            community_count=2,
            sentiment_summary={
                "distribution": {"positive": 50.0, "neutral": 20.0, "negative": 30.0}
            },
            **overrides,
        )


def test_ac11_below_minimum_history_is_unavailable_per_metric(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    _seed(db_session, project, MIN_HISTORY_POINTS - 1)

    body = api.get(f"/api/v1/projects/{project.id}/analyses/forecast").json()
    assert body["required_history"] == MIN_HISTORY_POINTS
    for metric in ("sentiment", "participants", "communities"):
        assert body[metric]["available"] is False
        assert body[metric]["predicted_next"] is None
        assert body[metric]["mae"] is None
        assert body[metric]["points_used"] == MIN_HISTORY_POINTS - 1


def test_ac9_and_ac10_forecast_and_loo_mae_at_minimum_history(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    _seed(db_session, project, MIN_HISTORY_POINTS)

    body = api.get(f"/api/v1/projects/{project.id}/analyses/forecast").json()
    participants = body["participants"]
    assert participants["available"] is True
    assert participants["points_used"] == MIN_HISTORY_POINTS
    # node_count goes 10, 11, 12, 13, 14 -> next is 15.
    assert participants["predicted_next"] == pytest.approx(15.0)
    assert participants["mae"] == pytest.approx(0.0, abs=1e-6)


def test_insufficient_data_rows_excluded_only_from_the_community_series(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    _seed(db_session, project, MIN_HISTORY_POINTS)
    # One more row, flagged insufficient_data — still usable for participants
    # and sentiment, dropped from communities.
    _analysis(
        db_session,
        project,
        created_at=datetime.now(UTC),
        node_count=99,
        community_count=1,
        insufficient_data=True,
        sentiment_summary={"distribution": {"positive": 50.0, "neutral": 20.0, "negative": 30.0}},
    )

    body = api.get(f"/api/v1/projects/{project.id}/analyses/forecast").json()
    assert body["participants"]["points_used"] == MIN_HISTORY_POINTS + 1
    assert body["sentiment"]["points_used"] == MIN_HISTORY_POINTS + 1
    assert body["communities"]["points_used"] == MIN_HISTORY_POINTS


def test_missing_and_other_users_project_answer_identically(
    api: TestClient, db_session: Session
) -> None:
    someone_else = make_user(db_session)
    theirs = _project(db_session, someone_else)

    not_yours = api.get(f"/api/v1/projects/{theirs.id}/analyses/forecast")
    missing = api.get(f"/api/v1/projects/{uuid.uuid4()}/analyses/forecast")
    assert not_yours.status_code == missing.status_code == 403
    assert not_yours.json() == missing.json()


def test_requires_a_token(db_session: Session, user: User) -> None:
    project = _project(db_session, user)
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app) as anon:
        assert anon.get(f"/api/v1/projects/{project.id}/analyses/forecast").status_code == 401
