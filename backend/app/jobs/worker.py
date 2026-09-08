"""RQ worker entrypoint.

Run with:  ``python -m app.jobs.worker``  (or ``rq worker orbitlink`` with the
right REDIS_URL).

On start it reaps any jobs orphaned by a previous crash, then schedules the
periodic reaper, then processes the queue.
"""

from __future__ import annotations

import logging

from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.jobs.queue import get_queue, get_redis
from app.jobs.reaper import reap_stale_jobs
from app.jobs.tasks import REAPER_INTERVAL, reap_stale_jobs_task

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")

    with SessionLocal() as session:
        reap_stale_jobs(session, timeout_minutes=settings.job_heartbeat_timeout_minutes)
        session.commit()
    get_queue().enqueue_in(REAPER_INTERVAL, reap_stale_jobs_task)

    worker = Worker([get_queue()], connection=get_redis())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
