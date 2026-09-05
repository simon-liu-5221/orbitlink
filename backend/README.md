# OrbitLink Backend

FastAPI + SQLAlchemy + Alembic + RQ. Package manager: [uv](https://docs.astral.sh/uv/).

## Local dev (without Docker)

```bash
uv sync
uv run alembic upgrade head          # needs a reachable Postgres
uv run uvicorn app.main:app --reload
uv run rq worker orbitlink           # or: uv run python -m app.jobs.worker
```

## Tests

```bash
uv run pytest -m "not integration"   # offline: no DB / Redis needed
uv run pytest --cov=app --cov-report=term-missing
```

Integration tests need Postgres + Redis. Easiest is the compose stack, which
publishes them on non-standard host ports (to avoid clashing with a locally
installed PostgreSQL / Redis):

```bash
docker compose up -d postgres redis           # from the repo root
export DATABASE_URL="postgresql+psycopg://orbitlink:orbitlink@localhost:55432/orbitlink"
export REDIS_URL="redis://localhost:56379/0"
uv run alembic upgrade head
uv run pytest                                  # full suite
```

## Checks (same as CI)

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run lint-imports                  # analysis/ layer purity (ADR-0003)
```

## Layout

| Path | Role |
|---|---|
| `app/api/` | routers — validation + delegation only |
| `app/core/` | config, logging |
| `app/db/` | models, session, `db/migrations/` (Alembic) |
| `app/jobs/` | RQ queue + worker (state machine lands in M2) |
| `app/services/` | orchestration (analysis ↔ db) |
| `app/analysis/` | **pure** algorithm layer — no db/http/fastapi imports |
| `app/ingest/` | YouTube Data API client (M2) |
