"""M0 integration check — requires Postgres and Redis (docker compose / CI services).

Run:  ``pytest -m integration``
Needs DATABASE_URL and REDIS_URL pointing at reachable services, and the
migrations applied (``alembic upgrade head``).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.session import engine

pytestmark = pytest.mark.integration


def test_healthz_reports_all_dependencies_up(client: TestClient) -> None:
    body = client.get("/healthz").json()
    assert body["dependencies"] == {"database": "up", "redis": "up"}
    assert body["status"] == "ok"


def test_migrations_applied() -> None:
    tables = set(inspect(engine).get_table_names())
    assert "alembic_version" in tables
