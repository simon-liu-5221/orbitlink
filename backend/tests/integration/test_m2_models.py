"""M2 schema — ORM model behaviour against a real database.

Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Analysis, AnalysisJob, Comment, Community, Node, Project, User
from app.db.models.project import DEV_PROJECT_ID
from app.db.models.user import DEV_USER_EMAIL, DEV_USER_ID
from app.jobs.state_machine import JobStatus

pytestmark = pytest.mark.integration


def _project(db: Session) -> Project:
    user = User(email=f"{uuid.uuid4()}@example.com")
    project = Project(name="Test project", user=user)
    db.add(project)
    db.flush()
    return project


def test_migration_seeds_the_dev_account(db_session: Session) -> None:
    user = db_session.get(User, DEV_USER_ID)
    assert user is not None and user.email == DEV_USER_EMAIL
    project = db_session.get(Project, DEV_PROJECT_ID)
    assert project is not None and project.user_id == DEV_USER_ID


def test_new_job_defaults(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(project=project, source_url="https://youtu.be/abc")
    db_session.add(job)
    db_session.flush()
    db_session.refresh(job)

    assert job.status == JobStatus.QUEUED.value
    assert job.status_enum is JobStatus.QUEUED
    assert job.is_terminal is False
    assert job.progress == 0
    assert job.params == {}
    assert job.created_at.tzinfo is not None  # timestamptz


def test_deleting_project_cascades_to_jobs_and_analyses(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(project=project, source_url="https://youtu.be/x")
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id)
    db_session.add(analysis)
    db_session.flush()
    project_id, job_id, analysis_id = project.id, job.id, analysis.id

    db_session.delete(project)
    db_session.flush()

    assert db_session.get(AnalysisJob, job_id) is None
    assert db_session.get(Analysis, analysis_id) is None
    assert db_session.get(Project, project_id) is None


def test_deleting_analysis_cascades_to_children(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(project=project, source_url="u")
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id, node_count=2)
    analysis.nodes = [
        Node(pseudonym="aaaa", engagement_score=8.1),
        Node(pseudonym="bbbb", engagement_score=3.4),
    ]
    analysis.communities = [Community(community_index=0, size=2)]
    analysis.comments = [
        Comment(external_ref="r1", author_pseudonym="aaaa", sentiment_label="positive")
    ]
    db_session.add(analysis)
    db_session.flush()
    analysis_id = analysis.id

    db_session.delete(analysis)
    db_session.flush()

    assert db_session.scalars(select(Node).where(Node.analysis_id == analysis_id)).all() == []
    assert (
        db_session.scalars(select(Community).where(Community.analysis_id == analysis_id)).all()
        == []
    )
    assert db_session.scalars(select(Comment).where(Comment.analysis_id == analysis_id)).all() == []


def test_node_pseudonym_is_unique_within_an_analysis(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(project=project, source_url="u")
    db_session.add(job)
    db_session.flush()
    analysis = Analysis(project_id=project.id, job_id=job.id)
    analysis.nodes = [Node(pseudonym="dup"), Node(pseudonym="dup")]
    db_session.add(analysis)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_one_analysis_per_job(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(project=project, source_url="u")
    db_session.add(job)
    db_session.flush()
    db_session.add(Analysis(project_id=project.id, job_id=job.id))
    db_session.flush()
    db_session.add(Analysis(project_id=project.id, job_id=job.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_job_heartbeat_and_terminal_flag(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=JobStatus.ANALYZING.value,
        progress=62,
        heartbeat_at=datetime.now(UTC),
    )
    db_session.add(job)
    db_session.flush()
    assert job.is_terminal is False

    job.status = JobStatus.COMPLETED.value
    db_session.flush()
    assert job.is_terminal is True
