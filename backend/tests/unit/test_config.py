import pytest

from app.core.config import Settings

_ENV_VARS = ["ENVIRONMENT", "DEBUG", "DATABASE_URL", "REDIS_URL"]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_development_safe() -> None:
    s = Settings(_env_file=None)
    assert s.environment == "development"
    assert s.is_production is False
    assert "localhost" in s.database_url


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")
    s = Settings(_env_file=None)
    assert s.is_production is True
    assert s.database_url.endswith("/x")
