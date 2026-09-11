"""PR-10 — GET /analyses/{id}/graph against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Analysis, AnalysisJob, Node, Project, User
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


def _analysis_with_graph(db: Session, owner: User, *, node_count: int = 25) -> Analysis:
    project = Project(name="P", user_id=owner.id)
    db.add(project)
    db.flush()
    job = AnalysisJob(
        project=project, source_url="u", status=JobStatus.COMPLETED.value, params=_JOB_PARAMS
    )
    db.add(job)
    db.flush()

    edges = [{"source": "a0", "target": "a1", "weight": 3}]
    analysis = Analysis(
        project_id=project.id,
        job_id=job.id,
        node_count=node_count,
        edge_count=len(edges),
        graph_edges=edges,
    )
    analysis.nodes = [
        Node(pseudonym=f"a{i}", pagerank=1.0 / (i + 1), engagement_score=float(i))
        for i in range(node_count)
    ]
    db.add(analysis)
    db.flush()
    return analysis


def test_graph_returns_every_node_not_just_top_twenty(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-1."""
    analysis = _analysis_with_graph(db_session, user, node_count=25)

    body = api.get(f"/api/v1/analyses/{analysis.id}/graph").json()

    assert len(body["nodes"]) == 25
    assert body["node_count"] == 25
    # ordered by pagerank descending
    pageranks = [n["pagerank"] for n in body["nodes"]]
    assert pageranks == sorted(pageranks, reverse=True)


def test_graph_edges_come_from_the_persisted_snapshot(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-2 — no graph is rebuilt; the endpoint just reads analyses.graph_edges."""
    analysis = _analysis_with_graph(db_session, user, node_count=5)

    body = api.get(f"/api/v1/analyses/{analysis.id}/graph").json()

    assert body["edges"] == [{"source": "a0", "target": "a1", "weight": 3}]
    assert body["edge_count"] == 1


def test_missing_and_other_users_analysis_answer_identically(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-3."""
    someone_else = make_user(db_session)
    theirs = _analysis_with_graph(db_session, someone_else)

    not_yours = api.get(f"/api/v1/analyses/{theirs.id}/graph")
    missing = api.get(f"/api/v1/analyses/{uuid.uuid4()}/graph")

    assert not_yours.status_code == missing.status_code == 404
    assert not_yours.json() == missing.json()


def test_graph_requires_a_token(db_session: Session, user: User) -> None:
    """AC-4."""
    analysis = _analysis_with_graph(db_session, user)

    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    with TestClient(app) as anon:
        resp = anon.get(f"/api/v1/analyses/{analysis.id}/graph")
    assert resp.status_code == 401


def test_analysis_with_no_edges_yet_returns_an_empty_list(
    api: TestClient, db_session: Session, user: User
) -> None:
    """Analyses persisted before this column existed default to []."""
    project = Project(name="P", user_id=user.id)
    db_session.add(project)
    db_session.flush()
    job = AnalysisJob(
        project=project, source_url="u", status=JobStatus.COMPLETED.value, params=_JOB_PARAMS
    )
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id, node_count=0)
    db_session.add(analysis)
    db_session.flush()

    body = api.get(f"/api/v1/analyses/{analysis.id}/graph").json()
    assert body["nodes"] == []
    assert body["edges"] == []
