"""FastAPI application factory.

Feature routers are added per-spec and live under ``/api/v1``.
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routers import admin, analyses, auth, feedback, health, projects
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import get_request_id, set_request_id

access_logger = logging.getLogger("app.access")
error_logger = logging.getLogger("app.errors")


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
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def observability(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Tag every request with a correlation id and log a structured
        access line (M7) — the id round-trips via ``X-Request-Id`` so a user
        can hand it to support and it can be grepped straight out of logs.
        """
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        set_request_id(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            access_logger.info(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                status_code,
                elapsed_ms,
            )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """The last line of defence against a bare 500 (UX-02): anything not
        already an ``HTTPException`` lands here, gets logged with its full
        traceback, and still gets a response with a concrete next step
        instead of an opaque crash.
        """
        request_id = get_request_id() or "unknown"
        error_logger.exception("unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "error_code": "INTERNAL_ERROR",
                    "message": (
                        "Something went wrong on our end. Try again in a "
                        "moment — if it keeps happening, contact support "
                        "with this request id."
                    ),
                    "request_id": request_id,
                }
            },
            headers={"X-Request-Id": request_id},
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(analyses.router)
    app.include_router(feedback.router)
    app.include_router(admin.router)

    return app


app = create_app()
