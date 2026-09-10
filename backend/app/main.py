"""FastAPI application factory.

Feature routers are added per-spec and live under ``/api/v1``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routers import analyses, auth, health, projects
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
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(analyses.router)

    return app


app = create_app()
