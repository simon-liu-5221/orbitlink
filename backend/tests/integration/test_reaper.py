"""AN-05 AC-8 — the stale-job reaper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob, Project
from app.jobs.reaper import reap_stale_jobs
from app.jobs.state_machine import JobStatus
from tests.support.auth import make_user

pytestmark = pytest.mark.integration


def _job(
    db: Session, *, status: JobStatus, heartbeat: datetime | None, created: datetime
) -> AnalysisJob:
    project = Project(name="P", user=make_user(db))
    db.add(project)
    db.flush()
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=status.value,
        heartbeat_at=heartbeat,
    )
    db.add(job)
    db.flush()
    db.execute(
        AnalysisJob.__table__.update().where(AnalysisJob.id == job.id).values(created_at=created)
    )
    db.refresh(job)
    return job


def test_reaps_a_job_whose_heartbeat_went_stale(db_session: Session) -> None:
    now = datetime.now(UTC)
    job = _job(
        db_session,
        status=JobStatus.ANALYZING,
        heartbeat=now - timedelta(minutes=45),
        created=now - timedelta(minutes=50),
    )
    reaped = reap_stale_jobs(db_session, timeout_minutes=30)

    assert job.id in reaped
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "WORKER_TIMEOUT"
    assert job.finished_at is not None


def test_leaves_a_freshly_beating_job_alone(db_session: Session) -> None:
    now = datetime.now(UTC)
    job = _job(
        db_session,
        status=JobStatus.ANALYZING,
        heartbeat=now - timedelta(minutes=2),
        created=now - timedelta(minutes=10),
    )
    assert reap_stale_jobs(db_session, timeout_minutes=30) == []
    db_session.refresh(job)
    assert job.status == JobStatus.ANALYZING.value


def test_reaps_a_queued_job_nothing_ever_picked_up(db_session: Session) -> None:
    now = datetime.now(UTC)
    job = _job(
        db_session,
        status=JobStatus.QUEUED,
        heartbeat=None,
        created=now - timedelta(hours=2),
    )
    assert job.id in reap_stale_jobs(db_session, timeout_minutes=30)
    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value


def test_never_touches_terminal_jobs(db_session: Session) -> None:
    now = datetime.now(UTC)
    job = _job(
        db_session,
        status=JobStatus.COMPLETED,
        heartbeat=now - timedelta(days=1),
        created=now - timedelta(days=1),
    )
    assert reap_stale_jobs(db_session, timeout_minutes=30) == []
    db_session.refresh(job)
    assert job.status == JobStatus.COMPLETED.value
