# OrbitLink Backend

FastAPI + SQLAlchemy + Alembic + RQ. Package manager: [uv](https://docs.astral.sh/uv/).

## Local dev (without Docker)

```bash
uv sync
uv run alembic upgrade head          # needs a reachable Postgres
uv run uvicorn app.main:app --reload
uv run python -m app.jobs.worker     # NOT `rq worker` — needs the startup reaper
```

The worker auto-selects `SimpleWorker` on Windows (no `os.fork`); Linux uses the
default forking `Worker`.

## Analysis API (M2, spec PR-01)

```
POST /api/v1/projects                         create a project
POST /api/v1/projects/{id}/analyses           -> 202 { job_id }   (start an analysis)
GET  /api/v1/jobs/{job_id}                     poll status + progress
POST /api/v1/jobs/{job_id}/cancel             cancel a running job
GET  /api/v1/analyses/{analysis_id}           summary + communities + top participants
```

Auth is a placeholder for M2: an `X-User-Id` header names the user; absent → the
seeded dev user. Real JWT auth is M3 (spec GU-01).

Sentiment uses a lexicon stand-in by default; `USE_REAL_SENTIMENT_MODEL=true`
plus `uv pip install transformers torch` switches to XLM-RoBERTa (decision B1).

Regenerate the frontend types after an API change:

```bash
uv run uvicorn app.main:app &        # then, from ../frontend:
npm run gen:api
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

## Algorithm validation

```bash
uv run python scripts/regen_validation.py   # regenerates docs/algorithm-validation.md numbers
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
