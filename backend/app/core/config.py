"""Application configuration.

All secrets and environment-specific values are read from the environment (or a
local ``.env`` file in development). Nothing here is hard-coded per rule 6 in
``CLAUDE.md``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: HS256 signs with a HMAC-SHA256 key; anything shorter than the digest adds
#: no security (RFC 7518 3.2).
MIN_SECRET_BYTES = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False

    # Infrastructure
    database_url: str = Field(
        default="postgresql+psycopg://orbitlink:orbitlink@localhost:5432/orbitlink",
        description="SQLAlchemy database URL (psycopg v3 driver).",
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    rq_queue_name: str = "orbitlink"

    # CORS — the deployed frontend origin(s)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Auth (M3, specs GU-01 / PR-02)
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    #: "Remember me" extends the refresh token to this many days (PR-02).
    refresh_token_remember_days: int = 30
    email_verification_hours: int = 24
    password_reset_hours: int = 1
    #: Where verification / reset links point — the frontend, not the API.
    frontend_base_url: str = "http://localhost:5173"
    #: "log" writes the message to the application log (default, no external
    #: dependency); "smtp" talks to MailHog locally or a real provider in prod.
    email_backend: Literal["log", "smtp"] = "log"
    email_from: str = "OrbitLink <no-reply@orbitlink.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    #: Refresh cookie is cross-site only when the frontend is not proxying /api.
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Secrets (no defaults in production; see .env.example)
    #: 32+ bytes so HS256's HMAC key is at least as long as its digest
    #: (RFC 7518 §3.2). Enforced in production by the validator below.
    jwt_secret: str = "dev-only-insecure-change-me-0123"
    pseudonym_key: str = "dev-only-insecure-change-me"
    youtube_api_key: str = ""

    # Analysis pipeline (M2)
    #: Use the real XLM-RoBERTa sentiment/toxicity models (ADR-0004) instead of
    #: the lexicon stand-in. Needs the ``sentiment`` extra installed. Default off
    #: (decision B1).
    use_real_sentiment_model: bool = False
    analysis_default_max_comments: int = 5000
    analysis_max_comments_cap: int = 50_000  # CAP-01
    analysis_channel_video_count: int = 10
    #: A job with no worker heartbeat for this long is reaped as failed (ADR-0002).
    job_heartbeat_timeout_minutes: int = 30

    @model_validator(mode="after")
    def _secrets_are_real_in_production(self) -> Settings:
        """Fail at boot rather than ship the dev placeholders (CLAUDE.md rule 6)."""
        if self.environment != "production":
            return self
        problems = [
            name
            for name, value in (
                ("JWT_SECRET", self.jwt_secret),
                ("PSEUDONYM_KEY", self.pseudonym_key),
            )
            if value.startswith("dev-only") or len(value.encode("utf-8")) < MIN_SECRET_BYTES
        ]
        if problems:
            raise ValueError(
                f"{', '.join(problems)} must be set to a random value of at least "
                f"{MIN_SECRET_BYTES} bytes in production"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def pseudonym_key_bytes(self) -> bytes:
        return self.pseudonym_key.encode("utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
