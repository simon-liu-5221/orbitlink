"""Application configuration.

All secrets and environment-specific values are read from the environment (or a
local ``.env`` file in development). Nothing here is hard-coded per rule 6 in
``CLAUDE.md``.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Secrets (no defaults in production; see .env.example)
    jwt_secret: str = "dev-only-insecure-change-me"
    pseudonym_key: str = "dev-only-insecure-change-me"
    youtube_api_key: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
