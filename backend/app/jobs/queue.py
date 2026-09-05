"""RQ queue and Redis connection helpers.

M0 provides only the plumbing. The analysis job state machine (ADR-0002) and
its handlers are implemented in M2.
"""

from functools import lru_cache

import redis
from rq import Queue

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url)


@lru_cache
def get_queue() -> Queue:
    settings = get_settings()
    return Queue(settings.rq_queue_name, connection=get_redis())
