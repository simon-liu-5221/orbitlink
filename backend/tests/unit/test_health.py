"""M0 smoke tests for /healthz — no database or redis required.

Without infrastructure the dependency checks report ``down`` and the overall
status is ``degraded``; the endpoint must still answer 200 with a valid schema.
"""

from fastapi.testclient import TestClient


def test_healthz_returns_200_with_expected_schema(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["version"]
    assert body["environment"]
    assert set(body["dependencies"]) == {"database", "redis"}
    assert all(v in {"up", "down"} for v in body["dependencies"].values())


def test_openapi_schema_is_served(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "OrbitLink API"
