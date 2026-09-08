"""Fail jobs whose worker went away (ADR-0002 / AN-05 AC-8).

A running job heartbeats at every stage. If that stops for
``timeout_minutes`` the worker is gone (crash, OOM, redeploy) — the job is
marked ``failed`` with ``error_code = WORKER_TIMEOUT`` so the user can retry.
Queued jobs older than the same window are reaped too (nothing ever picked
them up).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import AnalysisJob
from app.jobs.state_machine import TERMINAL, JobStatus

logger = logging.getLogger(__name__)


def reap_stale_jobs(session: Session, *, timeout_minutes: int = 30) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=timeout_minutes)
    live = [status.value for status in JobStatus if status not in TERMINAL]

    stale = session.scalars(
        select(AnalysisJob).where(
            AnalysisJob.status.in_(live),
            or_(
                AnalysisJob.heartbeat_at < cutoff,
                (AnalysisJob.heartbeat_at.is_(None)) & (AnalysisJob.created_at < cutoff),
            ),
        )
    ).all()

    reaped: list[uuid.UUID] = []
    for job in stale:
        job.status = JobStatus.FAILED.value
        job.error_code = "WORKER_TIMEOUT"
        job.error_message = f"no worker heartbeat for over {timeout_minutes} minutes"
        job.finished_at = now
        reaped.append(job.id)

    session.flush()
    if reaped:
        logger.warning("reaped %d stale job(s): %s", len(reaped), reaped)
    return reaped
