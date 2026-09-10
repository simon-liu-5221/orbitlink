"""PR-01 — the analysis HTTP API against a real database.

The RQ queue is faked (no redis job actually runs); the pipeline itself is
covered by test_analysis_service.py. Run:  ``pytest -m integration``
"""

from __future__ import annotations

import types
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.routers import analyses as analyses_router
from app.core.config import Settings
from app.db.models import Analysis, AnalysisJob, Community, Node, Project, User
from app.jobs.state_machine import JobStatus
from app.main import create_app
from tests.support.auth import bearer, make_user

pytestmark = pytest.mark.integration


class _FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[Any, ...]] = []

    def enqueue(self, fn: Any, *args: Any) -> Any:
        self.enqueued.append((fn, *args))
        return types.SimpleNamespace(id=f"rq-{uuid.uuid4()}")

    def remove(self, _job_id: str) -> None:
        pass


@pytest.fixture
def fake_queue(monkeypatch: pytest.MonkeyPatch) -> _FakeQueue:
    queue = _FakeQueue()
    monkeypatch.setattr(analyses_router, "get_queue", lambda: queue)
    return queue


@pytest.fixture
def user(db_session: Session) -> User:
    return make_user(db_session)


@pytest.fixture
def api(db_session: Session, user: User) -> TestClient:
    """A client already signed in as ``user`` (M3: a real bearer token)."""
    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.rate_limit_analyses] = lambda: None
    with TestClient(app, headers=bearer(user)) as client:
        return client


def _project(db: Session, user: User) -> Project:
    project = Project(name="P", user_id=user.id)
    db.add(project)
    db.flush()
    return project


def test_start_analysis_returns_202_with_a_queued_job(
    api: TestClient, db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    project = _project(db_session, user)
    resp = api.post(
        f"/api/v1/projects/{project.id}/analyses",
        json={"source_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert resp.status_code == 202
    body = resp.json()
    job = db_session.get(AnalysisJob, uuid.UUID(body["job_id"]))
    assert job is not None
    assert job.status == JobStatus.QUEUED.value
    assert len(fake_queue.enqueued) == 1


def test_bad_url_returns_422_with_error_code(
    api: TestClient, db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    project = _project(db_session, user)
    resp = api.post(
        f"/api/v1/projects/{project.id}/analyses", json={"source_url": "https://vimeo.com/1"}
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "INVALID_URL"


def test_over_the_comment_cap_returns_422(
    api: TestClient, db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    project = _project(db_session, user)
    resp = api.post(
        f"/api/v1/projects/{project.id}/analyses",
        json={"source_url": "https://youtu.be/dQw4w9WgXcQ", "max_comments": 999999},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "COMMENT_CAP_EXCEEDED"


def test_second_live_job_returns_409(
    api: TestClient, db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    project = _project(db_session, user)
    url = "https://youtu.be/dQw4w9WgXcQ"
    assert (
        api.post(f"/api/v1/projects/{project.id}/analyses", json={"source_url": url}).status_code
        == 202
    )
    resp = api.post(f"/api/v1/projects/{project.id}/analyses", json={"source_url": url})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "PROJECT_BUSY"


def test_another_users_project_is_403_and_does_not_leak_existence(
    api: TestClient, db_session: Session, fake_queue: _FakeQueue
) -> None:
    other = make_user(db_session)
    their_project = _project(db_session, other)

    real = api.post(
        f"/api/v1/projects/{their_project.id}/analyses",
        json={"source_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    missing = api.post(
        f"/api/v1/projects/{uuid.uuid4()}/analyses",
        json={"source_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert real.status_code == missing.status_code == 403


def test_requests_without_a_valid_token_are_401(
    api: TestClient, db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    """PR-01 AC-9, now for real: no token, junk token, wrong signature."""
    project = _project(db_session, user)
    url = f"/api/v1/projects/{project.id}/analyses"
    body = {"source_url": "https://youtu.be/dQw4w9WgXcQ"}

    anonymous = api.post(url, json=body, headers={"Authorization": ""})
    junk = api.post(url, json=body, headers={"Authorization": "Bearer not-a-jwt"})
    wrong_key = api.post(
        url,
        json=body,
        headers=bearer(user, Settings(_env_file=None, jwt_secret="a-different-secret")),
    )
    basic = api.get("/api/v1/projects", headers={"Authorization": "Basic Zm9vOmJhcg=="})

    assert [r.status_code for r in (anonymous, junk, wrong_key, basic)] == [401, 401, 401, 401]


def test_token_for_a_deleted_user_is_401(api: TestClient, db_session: Session) -> None:
    """Also exercises the real get_db generator — no override on this client."""
    ghost = make_user(db_session)
    db_session.delete(ghost)
    db_session.flush()

    app = create_app()  # deliberately no dependency_overrides
    with TestClient(app) as client:
        assert client.get("/api/v1/projects", headers=bearer(ghost)).status_code == 401


def test_job_status_is_pollable(api: TestClient, db_session: Session, user: User) -> None:
    project = _project(db_session, user)
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=JobStatus.ANALYZING.value,
        progress=62,
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 1,
            "channel_video_count": 1,
        },
    )
    db_session.add(job)
    db_session.flush()

    body = api.get(f"/api/v1/jobs/{job.id}").json()
    assert body["status"] in {s.value for s in JobStatus}
    assert isinstance(body["progress"], int)
    assert 0 <= body["progress"] <= 100


def test_cancel_marks_job_cancelled(api: TestClient, db_session: Session, user: User) -> None:
    project = _project(db_session, user)
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=JobStatus.FETCHING.value,
        progress=10,
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 1,
            "channel_video_count": 1,
        },
    )
    db_session.add(job)
    db_session.flush()

    resp = api.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == JobStatus.CANCELLED.value

    resp2 = api.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp2.status_code == 409


def test_get_analysis_returns_summary_and_top_participants(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _project(db_session, user)
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=JobStatus.COMPLETED.value,
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 1,
            "channel_video_count": 1,
        },
    )
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(
        project_id=project.id,
        job_id=job.id,
        modularity=0.42,
        node_count=3,
        community_count=1,
        sentiment_summary={"model": "lexicon-standin", "distribution": {}},
    )
    analysis.nodes = [
        Node(pseudonym="aa", engagement_score=9.0, influence_rank=1),
        Node(pseudonym="bb", engagement_score=4.0, influence_rank=2),
    ]
    analysis.communities = [Community(community_index=0, size=3)]
    db_session.add(analysis)
    db_session.flush()

    body = api.get(f"/api/v1/analyses/{analysis.id}").json()
    assert body["modularity"] == 0.42
    assert body["sentiment_summary"]["model"] == "lexicon-standin"
    assert [n["influence_rank"] for n in body["top_influencers"]] == [1, 2]
    assert body["top_engaged"][0]["pseudonym"] == "aa"
    assert len(body["communities"]) == 1


def test_project_create_list_get(api: TestClient, db_session: Session, user: User) -> None:
    created = api.post("/api/v1/projects", json={"name": "My channel study"})
    assert created.status_code == 201
    project_id = created.json()["id"]

    listing = api.get("/api/v1/projects").json()
    assert any(p["id"] == project_id for p in listing)
    assert api.get(f"/api/v1/projects/{project_id}").json()["name"] == "My channel study"


def test_project_of_another_user_is_403(api: TestClient, db_session: Session) -> None:
    other = make_user(db_session)
    theirs = _project(db_session, other)
    assert api.get(f"/api/v1/projects/{theirs.id}").status_code == 403


def test_missing_job_and_analysis_are_404(api: TestClient) -> None:
    assert api.get(f"/api/v1/jobs/{uuid.uuid4()}").status_code == 404
    assert api.get(f"/api/v1/analyses/{uuid.uuid4()}").status_code == 404


def test_enqueue_failure_marks_job_failed_and_returns_503(
    api: TestClient, db_session: Session, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenQueue:
        def enqueue(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("redis down")

    monkeypatch.setattr(analyses_router, "get_queue", lambda: _BrokenQueue())
    project = _project(db_session, user)
    resp = api.post(
        f"/api/v1/projects/{project.id}/analyses",
        json={"source_url": "https://youtu.be/dQw4w9WgXcQ"},
    )
    assert resp.status_code == 503
    job = db_session.scalars(
        select(AnalysisJob).where(AnalysisJob.project_id == project.id)
    ).first()
    assert job is not None and job.status == JobStatus.FAILED.value
    assert job.error_code == "ENQUEUE_FAILED"


def test_rate_limit_kicks_in_at_eleven(
    db_session: Session, user: User, fake_queue: _FakeQueue
) -> None:
    from app.jobs.queue import get_redis

    try:
        get_redis().delete("ratelimit:analyses:testclient")
    except Exception:
        pytest.skip("redis unavailable")

    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session  # real rate_limit dependency
    project = _project(db_session, user)
    with TestClient(app) as client:
        codes = [
            client.post(
                f"/api/v1/projects/{project.id}/analyses",
                json={"source_url": "https://vimeo.com/1"},  # 422 is fine, still counts
            ).status_code
            for _ in range(11)
        ]
    assert codes[-1] == 429
    assert codes.count(429) == 1
