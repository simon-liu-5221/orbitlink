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

## Project & analysis API (specs PR-07, PR-01)

```
POST   /api/v1/projects                       create a project
GET    /api/v1/projects?q=&include_archived=  list / search your projects
GET    /api/v1/projects/{id}                  one project
PATCH  /api/v1/projects/{id}                  rename
POST   /api/v1/projects/{id}/archive          soft-archive (reversible, hidden from the default list)
POST   /api/v1/projects/{id}/unarchive        restore
DELETE /api/v1/projects/{id}                  permanent; cascades; 409 if a job is running
GET    /api/v1/projects/{id}/jobs             this project's analysis-job history
POST   /api/v1/projects/{id}/analyses         -> 202 { job_id }   (start an analysis)
GET    /api/v1/jobs/{job_id}                  poll status + progress
POST   /api/v1/jobs/{job_id}/cancel           cancel a running job
GET    /api/v1/analyses/{analysis_id}         summary + communities + top participants
GET    /api/v1/analyses/{analysis_id}/graph   every node + edge (for the network graph, PR-10)
```

Every project-scoped route answers 403 identically whether the project belongs
to another user or does not exist (NFR SEC-02).

```
POST /api/v1/auth/register                    create an account (email confirmation required)
GET  /api/v1/auth/verify?token=...            confirm the email address
POST /api/v1/auth/resend-verification         send a fresh confirmation link
POST /api/v1/auth/forgot-password             email a one-time password-reset link
POST /api/v1/auth/reset-password              set a new password, sign every device out
POST /api/v1/auth/login                       access token in the body, refresh token in a cookie
POST /api/v1/auth/refresh                     rotate the session
POST /api/v1/auth/logout                      revoke the refresh token
GET  /api/v1/auth/me                          the signed-in user
```

Auth (M3, specs GU-01 / PR-02): every endpoint above `/api/v1/auth` needs an
`Authorization: Bearer <access token>` header. The access token is a 15-minute
HS256 JWT the frontend keeps in memory; the refresh token is an opaque secret in
an httpOnly cookie, stored only as a SHA-256 digest and rotated on every use.

Outbound email has a pluggable backend. The default (`EMAIL_BACKEND=log`) writes
the message to the application log, so nothing external is needed to develop or
run CI; `EMAIL_BACKEND=smtp` points at MailHog in compose (inbox at
http://localhost:8025) or a real provider in production.

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
export DATABASE_URL="postgresql+psycopg://orbitlink:orbitlink@localhost:15432/orbitlink"
export REDIS_URL="redis://localhost:16379/0"
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
