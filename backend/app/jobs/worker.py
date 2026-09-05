"""RQ worker entrypoint.

Run with:  ``python -m app.jobs.worker``  (or ``rq worker orbitlink`` with the
right REDIS_URL). M0 just proves the worker process boots and connects; M2 adds
the heartbeat and job handlers.
"""

from __future__ import annotations

from rq import Worker

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.jobs.queue import get_queue, get_redis


def main() -> None:
    settings = get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")
    worker = Worker([get_queue()], connection=get_redis())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
