# Load test (M7 — CAP-02, PERF-01)

Runs against the local docker-compose stack, not the live Render deployment —
Render free tier's cold starts and shared-CPU throttling would dominate the
numbers and tell you nothing about the app's own performance (see
`docs/nfr.md` / `docs/roadmap.md` for that decision).

## Prerequisites

- `docker compose up -d postgres redis` (from the repo root)
- `cd backend && uv run alembic upgrade head`
- `k6` via Docker — no local install needed (see below)

## Run it

```bash
# 1. start the API
cd backend
export DATABASE_URL="postgresql+psycopg://orbitlink:orbitlink@localhost:15432/orbitlink"
export REDIS_URL="redis://localhost:16379/0"
uv run uvicorn app.main:app --port 8000 &

# 2. seed a user, 6 completed analyses, and 5 "active" jobs (CAP-02's
#    concurrent-analysis condition — see seed.py's docstring for why these
#    are DB rows rather than real YouTube ingestion)
uv run python ../loadtest/seed.py > ../loadtest/seed-data.json

# 3. run k6 against the host API (host.docker.internal is Docker Desktop's
#    gateway back to the host; MSYS_NO_PATHCONV avoids Git Bash mangling the
#    -v/-w paths on Windows)
cd ../loadtest
MSYS_NO_PATHCONV=1 docker run --rm -i --add-host=host.docker.internal:host-gateway \
  -v "$(pwd):/scripts" -w /scripts grafana/k6 run pageload.js

# 4. clean up the seeded user (cascades to their projects/jobs/analyses)
cd ../backend
uv run python ../loadtest/cleanup.py
```

## What it measures

20 virtual users (CAP-02) continuously hit the read-heavy "page load" endpoints
(list projects, open a project, its jobs, its history, its forecast, one
analysis result) while 5 of the seeded projects sit with a job in an
`analyzing` state, standing in for CAP-02's "5 concurrent analysis jobs"
condition. Thresholds assert PERF-01 (p95 < 300ms) per endpoint and an overall
failure rate under 1%.

See `docs/nfr.md`'s CAP-02/PERF-01 rows for the last recorded run's numbers.
