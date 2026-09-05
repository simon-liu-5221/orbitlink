"""Health check endpoint.

``/healthz`` reports liveness plus the reachability of Postgres and Redis. The
frontend M0 skeleton renders this so the deploy pipeline can be verified end to
end (roadmap M0 acceptance criterion).
"""

from typing import Literal

import redis
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])

Status = Literal["ok", "degraded"]
DependencyState = Literal["up", "down"]


class HealthResponse(BaseModel):
    status: Status
    version: str
    environment: str
    dependencies: dict[str, DependencyState]


def _check_database() -> DependencyState:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "up"
    except Exception:  # noqa: BLE001 — health check must never raise
        return "down"


def _check_redis() -> DependencyState:
    settings = get_settings()
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        return "up"
    except Exception:  # noqa: BLE001
        return "down"


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    settings = get_settings()
    deps: dict[str, DependencyState] = {
        "database": _check_database(),
        "redis": _check_redis(),
    }
    status: Status = "ok" if all(v == "up" for v in deps.values()) else "degraded"
    return HealthResponse(
        status=status,
        version=__version__,
        environment=settings.environment,
        dependencies=deps,
    )
