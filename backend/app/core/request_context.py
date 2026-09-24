"""Request-scoped correlation id (M7 observability).

A `ContextVar` so every log line emitted while handling a request — however
deep in the call stack — can be tagged with the same id automatically,
without threading it through every function signature. Each ASGI request
runs in its own task-local context, so setting a fresh value per request
(done once, in the middleware) is enough; nothing needs to reset it.
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)
