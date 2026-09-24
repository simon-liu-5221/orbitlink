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
GET    /api/v1/projects/{id}/analyses         every completed analysis, oldest first (trend charts, AN-06)
GET    /api/v1/projects/{id}/analyses/forecast linear-regression extrapolation + leave-one-out MAE per metric (AN-06 phase 2)
POST   /api/v1/projects/{id}/analyses         -> 202 { job_id }   (start an analysis)
GET    /api/v1/jobs/{job_id}                  poll status + progress
POST   /api/v1/jobs/{job_id}/cancel           cancel a running job
GET    /api/v1/analyses/{analysis_id}         summary + communities + top participants
GET    /api/v1/analyses/{analysis_id}/graph   every node + edge (for the network graph, PR-10)
POST   /api/v1/feedback                       submit product feedback (rating 1-5 + optional comment, PR-12)
GET    /api/v1/admin/users?q=&include_suspended= admin: list/search users (AD-01)
POST   /api/v1/admin/users/{id}/suspend       admin: suspend an account (AD-01)
POST   /api/v1/admin/users/{id}/unsuspend     admin: restore a suspended account (AD-01)
GET    /api/v1/admin/feedback                 admin: every feedback submission (AD-02)
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

Admin (M5, specs AD-01/AD-02): a `role` column on `users`, checked by a
`require_admin` dependency layered on the same JWT auth — no separate admin
login. Nothing in the app can self-promote; the only way to become an admin is

```bash
uv run python scripts/promote_admin.py someone@example.com
```

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

## Observability & error handling (M7)

Every response carries an `X-Request-Id` header (`app/main.py`'s `observability`
middleware) — reused from the client if it sent one, generated otherwise. The
same id tags every structured JSON log line emitted while handling that
request (`app/core/request_context.py` + `JsonFormatter`), so a single
request's logs across routers/services/jobs can be grepped out by id alone.

A global `Exception` handler is the last line of defence against a bare 500
(UX-02): anything not already an `HTTPException` gets logged with its full
traceback and still returns a structured `{"detail": {"error_code":
"INTERNAL_ERROR", "message": ..., "request_id": ...}}` body — ordinary
`HTTPException`s (401/403/404/409/422 etc.) are untouched, since FastAPI
routes a handler registered on the base `Exception` class through Starlette's
`ServerErrorMiddleware`, not `ExceptionMiddleware`.

Sentry was considered and deliberately skipped — no live traffic yet to
justify the external dependency; structured logs are enough for now.

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
