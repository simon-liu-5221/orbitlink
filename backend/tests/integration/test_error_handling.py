"""M7 observability — request-id correlation and the global exception
handler that keeps a genuine bug from surfacing as a bare 500 (UX-02).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.integration


def test_unhandled_exception_returns_structured_json_not_a_bare_500() -> None:
    app = create_app()

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__boom")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail["error_code"] == "INTERNAL_ERROR"
    assert detail["message"]
    assert detail["request_id"]
    assert response.headers["x-request-id"] == detail["request_id"]


def test_request_id_is_echoed_back_when_the_client_supplies_one() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"X-Request-Id": "fixed-test-id"})
    assert response.headers["x-request-id"] == "fixed-test-id"


def test_request_id_is_generated_when_the_client_does_not_supply_one() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.headers["x-request-id"]


def test_two_requests_without_a_client_id_get_different_ids() -> None:
    app = create_app()
    with TestClient(app) as client:
        first = client.get("/healthz")
        second = client.get("/healthz")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_an_ordinary_http_exception_is_unaffected_by_the_catch_all_handler() -> None:
    """A 401/403/404 etc. still goes through FastAPI's normal handling —
    the catch-all only wires into the truly-unhandled path (M7 implementation
    note: registering on ``Exception`` routes through Starlette's
    ServerErrorMiddleware, not ExceptionMiddleware, so HTTPException is
    untouched)."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert "error_code" not in response.json().get("detail", {})
