import pytest
from pydantic import ValidationError

from app.core.config import MIN_SECRET_BYTES, Settings

_ENV_VARS = [
    "ENVIRONMENT",
    "DEBUG",
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "PSEUDONYM_KEY",
]

_REAL_SECRETS = {
    "jwt_secret": "j" * MIN_SECRET_BYTES,
    "pseudonym_key": "p" * MIN_SECRET_BYTES,
}


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
    s = Settings(_env_file=None, **_REAL_SECRETS)
    assert s.is_production is True
    assert s.database_url.endswith("/x")


def test_production_refuses_the_dev_placeholder_secrets() -> None:
    """CLAUDE.md rule 6 — better a failed boot than a deployment signing with
    a secret that is public knowledge."""
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, environment="production")
    message = str(caught.value)
    assert "JWT_SECRET" in message
    assert "PSEUDONYM_KEY" in message


def test_production_refuses_a_short_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="a" * (MIN_SECRET_BYTES - 1),
            pseudonym_key="p" * MIN_SECRET_BYTES,
        )


def test_non_production_tolerates_the_placeholders() -> None:
    for environment in ("development", "test", "staging"):
        assert Settings(_env_file=None, environment=environment).jwt_secret
