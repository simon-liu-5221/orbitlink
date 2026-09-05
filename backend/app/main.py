"""FastAPI application factory.

M0 wires only the health router. Feature routers are added per-spec in later
milestones and always live under ``/api/v1``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routers import health
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")

    app = FastAPI(
        title="OrbitLink API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    return app


app = create_app()
