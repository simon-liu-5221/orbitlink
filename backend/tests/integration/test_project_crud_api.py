"""PR-07 — project CRUD (rename / archive / delete / search) + SEC-02 isolation.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import Analysis, AnalysisJob, Comment, Community, Node, Project, User
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
    app.dependency_overrides[deps.rate_limit_analyses] = lambda: None
    with TestClient(app, headers=bearer(user)) as client:
        return client


def _make_project(
    db: Session, owner: User, name: str = "Project", *, archived: bool = False
) -> Project:
    project = Project(name=name, user_id=owner.id)
    if archived:
        project.archived_at = datetime.now(UTC)
    db.add(project)
    db.flush()
    return project


# --- AC-1 / AC-2 : create + validation ------------------------------


def test_create_returns_201_and_belongs_to_the_caller(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-1."""
    resp = api.post("/api/v1/projects", json={"name": "My channel study"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["archived_at"] is None

    row = db_session.get(Project, uuid.UUID(body["id"]))
    assert row is not None and row.user_id == user.id


@pytest.mark.parametrize("name", ["", "   ", "\t\n", "x" * 201])
def test_bad_names_are_422(api: TestClient, db_session: Session, user: User, name: str) -> None:
    """AC-2."""
    assert api.post("/api/v1/projects", json={"name": name}).status_code == 422
    project = _make_project(db_session, user)
    assert api.patch(f"/api/v1/projects/{project.id}", json={"name": name}).status_code == 422


def test_create_strips_surrounding_whitespace(api: TestClient) -> None:
    body = api.post("/api/v1/projects", json={"name": "  Trimmed  "}).json()
    assert body["name"] == "Trimmed"


# --- AC-3 : search -------------------------------------------------


def test_search_is_case_insensitive_substring(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-3."""
    _make_project(db_session, user, "Climate discourse on YouTube")
    _make_project(db_session, user, "Gaming channel")
    _make_project(db_session, user, "Politics")

    hits = api.get("/api/v1/projects", params={"q": "CLIMATE"}).json()
    assert [p["name"] for p in hits] == ["Climate discourse on YouTube"]


def test_search_escapes_like_wildcards(api: TestClient, db_session: Session, user: User) -> None:
    _make_project(db_session, user, "100% organic")
    _make_project(db_session, user, "anything at all")

    # a literal "%" must match literally, not as a wildcard
    hits = api.get("/api/v1/projects", params={"q": "100%"}).json()
    assert [p["name"] for p in hits] == ["100% organic"]


# --- AC-4 / AC-6 / AC-7 : archive lifecycle -----------------------


def test_default_list_hides_archived(api: TestClient, db_session: Session, user: User) -> None:
    """AC-4."""
    _make_project(db_session, user, "Active one")
    _make_project(db_session, user, "Active two")
    _make_project(db_session, user, "Old one", archived=True)

    default = api.get("/api/v1/projects").json()
    assert {p["name"] for p in default} == {"Active one", "Active two"}

    everything = api.get("/api/v1/projects", params={"include_archived": "true"}).json()
    assert len(everything) == 3


def test_archive_is_idempotent(api: TestClient, db_session: Session, user: User) -> None:
    """AC-6."""
    project = _make_project(db_session, user)

    first = api.post(f"/api/v1/projects/{project.id}/archive")
    assert first.status_code == 200
    stamp = first.json()["archived_at"]
    assert stamp is not None
    assert not any(p["id"] == str(project.id) for p in api.get("/api/v1/projects").json())

    second = api.post(f"/api/v1/projects/{project.id}/archive")
    assert second.status_code == 200
    assert second.json()["archived_at"] == stamp


def test_unarchive_restores_to_the_default_list(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-7."""
    project = _make_project(db_session, user, archived=True)

    resp = api.post(f"/api/v1/projects/{project.id}/unarchive")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is None
    assert any(p["id"] == str(project.id) for p in api.get("/api/v1/projects").json())


def test_unarchive_an_active_project_is_idempotent(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _make_project(db_session, user)
    assert api.post(f"/api/v1/projects/{project.id}/unarchive").status_code == 200


# --- AC-5 : rename ------------------------------------------------


def test_rename_persists(api: TestClient, db_session: Session, user: User) -> None:
    """AC-5."""
    project = _make_project(db_session, user, "Before")
    resp = api.patch(f"/api/v1/projects/{project.id}", json={"name": "After"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "After"
    assert api.get(f"/api/v1/projects/{project.id}").json()["name"] == "After"


def test_rename_works_on_an_archived_project(
    api: TestClient, db_session: Session, user: User
) -> None:
    project = _make_project(db_session, user, archived=True)
    assert api.patch(f"/api/v1/projects/{project.id}", json={"name": "Renamed"}).status_code == 200


# --- AC-8 / AC-9 : delete ---------------------------------------


def test_delete_cascades_to_all_analysis_data(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-8."""
    project = _make_project(db_session, user)
    job = AnalysisJob(
        project=project, source_url="u", status=JobStatus.COMPLETED.value, params=_JOB_PARAMS
    )
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id, node_count=1)
    analysis.nodes = [Node(pseudonym="aaaa", engagement_score=1.0)]
    analysis.communities = [Community(community_index=0, size=1)]
    analysis.comments = [Comment(external_ref="r1", author_pseudonym="aaaa")]
    db_session.add(analysis)
    db_session.flush()
    ids = {
        "project": project.id,
        "job": job.id,
        "analysis": analysis.id,
        "node": analysis.nodes[0].id,
    }

    assert api.delete(f"/api/v1/projects/{project.id}").status_code == 204

    db_session.expire_all()
    assert db_session.get(Project, ids["project"]) is None
    assert db_session.get(AnalysisJob, ids["job"]) is None
    assert db_session.get(Analysis, ids["analysis"]) is None
    assert db_session.scalars(select(Node).where(Node.analysis_id == ids["analysis"])).all() == []
    assert (
        db_session.scalars(select(Community).where(Community.analysis_id == ids["analysis"])).all()
        == []
    )
    assert (
        db_session.scalars(select(Comment).where(Comment.analysis_id == ids["analysis"])).all()
        == []
    )


def test_delete_refuses_a_project_with_a_live_job(
    api: TestClient, db_session: Session, user: User
) -> None:
    """AC-9."""
    project = _make_project(db_session, user)
    db_session.add(
        AnalysisJob(
            project=project, source_url="u", status=JobStatus.ANALYZING.value, params=_JOB_PARAMS
        )
    )
    db_session.flush()

    resp = api.delete(f"/api/v1/projects/{project.id}")
    assert resp.status_code == 409
    assert resp.json()["detail"]["error_code"] == "PROJECT_BUSY"
    assert db_session.get(Project, project.id) is not None


# --- AC-13 : job history ---------------------------------------


def test_project_jobs_lists_newest_first(api: TestClient, db_session: Session, user: User) -> None:
    """AC-13."""
    project = _make_project(db_session, user)
    base = datetime.now(UTC) - timedelta(hours=1)
    # an older finished run, then a newer one still going
    for offset, status_value, progress in (
        (0, JobStatus.COMPLETED.value, 100),
        (5, JobStatus.ANALYZING.value, 40),
    ):
        db_session.add(
            AnalysisJob(
                project=project,
                source_url="u",
                status=status_value,
                progress=progress,
                params=_JOB_PARAMS,
                created_at=base + timedelta(minutes=offset),
            )
        )
        db_session.flush()

    body = api.get(f"/api/v1/projects/{project.id}/jobs").json()
    assert len(body) == 2
    assert body[0]["progress"] == 40  # newest first
    assert body[1]["progress"] == 100
    assert {row["status"] for row in body} == {"completed", "analyzing"}


# --- AC-10 / AC-11 : SEC-02 isolation --------------------------

#: (method, path suffix, json body or None) for every project-scoped endpoint.
_ENDPOINTS: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "", None),
    ("PATCH", "", {"name": "hijacked"}),
    ("POST", "/archive", None),
    ("POST", "/unarchive", None),
    ("DELETE", "", None),
    ("GET", "/jobs", None),
    ("POST", "/analyses", {"source_url": "https://youtu.be/dQw4w9WgXcQ"}),
]


def _call(api: TestClient, method: str, url: str, body: dict[str, Any] | None) -> httpx.Response:
    fn: Callable[..., httpx.Response] = getattr(api, method.lower())
    return fn(url, json=body) if body is not None else fn(url)


@pytest.mark.parametrize("method,suffix,body", _ENDPOINTS)
def test_another_users_project_is_403_on_every_endpoint(
    api: TestClient,
    db_session: Session,
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
) -> None:
    """AC-10 (SEC-02) — user B cannot touch user A's project through any route."""
    someone_else = make_user(db_session)
    theirs = _make_project(db_session, someone_else)

    resp = _call(api, method, f"/api/v1/projects/{theirs.id}{suffix}", body)
    assert resp.status_code == 403


@pytest.mark.parametrize("method,suffix,body", _ENDPOINTS)
def test_missing_project_is_indistinguishable_from_not_yours(
    api: TestClient,
    db_session: Session,
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
) -> None:
    """AC-11 — a project that does not exist answers exactly like one that isn't yours."""
    someone_else = make_user(db_session)
    theirs = _make_project(db_session, someone_else)
    ghost_id = uuid.uuid4()

    not_yours = _call(api, method, f"/api/v1/projects/{theirs.id}{suffix}", body)
    missing = _call(api, method, f"/api/v1/projects/{ghost_id}{suffix}", body)
    assert not_yours.status_code == missing.status_code == 403
    assert not_yours.json() == missing.json()


# --- AC-12 : auth required ------------------------------------


@pytest.mark.parametrize("method,suffix,body", _ENDPOINTS)
def test_every_endpoint_needs_a_token(
    db_session: Session, method: str, suffix: str, body: dict[str, Any] | None
) -> None:
    """AC-12."""
    owner = make_user(db_session)
    project = _make_project(db_session, owner)

    app = create_app()
    app.dependency_overrides[deps.get_db] = lambda: db_session
    app.dependency_overrides[deps.rate_limit_analyses] = lambda: None
    with TestClient(app) as anon:  # no Authorization header
        resp = _call(anon, method, f"/api/v1/projects/{project.id}{suffix}", body)
    assert resp.status_code == 401
