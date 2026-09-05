# syntax=docker/dockerfile:1

# ---- builder -------------------------------------------------------------
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir "uv>=0.5,<0.6"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first for layer caching. uv.lock is optional (falls back
# to resolving from pyproject.toml if it is not committed yet).
COPY pyproject.toml ./
COPY uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# ---- runtime -----------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# Default: API. The worker overrides the command (see fly.toml / compose).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
