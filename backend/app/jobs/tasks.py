"""RQ task entrypoints. Thin: open a session, call a service, commit."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingest.youtube import YouTubeClient
from app.jobs.queue import get_queue
from app.jobs.reaper import reap_stale_jobs
from app.services.analysis_service import SentimentModel, run_analysis
from app.services.sentiment_factory import build_sentiment_analyzer

logger = logging.getLogger(__name__)

REAPER_INTERVAL = timedelta(minutes=5)


def run_analysis_job(job_id: str) -> str:
    """Run one analysis job to a terminal status; returns that status."""
    settings = get_settings()
    analyzer, label = build_sentiment_analyzer(settings)
    with SessionLocal() as session:
        job = run_analysis(
            session,
            uuid.UUID(job_id),
            youtube_client=YouTubeClient(settings.youtube_api_key),
            sentiment=SentimentModel(analyzer=analyzer, label=label),
            pseudonym_key=settings.pseudonym_key_bytes,
        )
        session.commit()
        return job.status


def reap_stale_jobs_task() -> int:
    """Reap orphaned jobs, then re-enqueue itself so reaping stays periodic."""
    settings = get_settings()
    with SessionLocal() as session:
        reaped = reap_stale_jobs(session, timeout_minutes=settings.job_heartbeat_timeout_minutes)
        session.commit()
    get_queue().enqueue_in(REAPER_INTERVAL, reap_stale_jobs_task)
    return len(reaped)
