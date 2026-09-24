"""M7 — seeds data for the k6 page-load test (CAP-02, PERF-01) and prints a
JSON blob k6 reads to know what to hit.

Run against the same DATABASE_URL the app itself uses (docker-compose's
Postgres by default):

    cd backend
    uv run python ../loadtest/seed.py > ../loadtest/seed-data.json

What it creates:
- one verified user with a long-lived access token (skips the register/verify
  email flow entirely — this is a throwaway load-test fixture, not a real
  account)
- one "primary" project with 6 completed analyses (>=5 so AN-06's forecast
  endpoint has enough history to be interesting), each with ~30 nodes and 3
  communities so GET /analyses/{id} does a realistic amount of work
- 5 more projects, each with one AnalysisJob sitting in an *active* status
  (``analyzing``) — this stands in for CAP-02's "5 concurrent analysis jobs"
  condition. Real concurrent ingestion needs YouTube API quota and a live
  worker, neither of which a repeatable local load test can depend on; active
  DB rows create the same read/lock pressure the page-load endpoints would
  actually feel while jobs are in flight, which is the thing CAP-02 cares
  about (PERF-01 not degrading), so this is an honest stand-in, not a shortcut
  around the real question.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models import Analysis, AnalysisJob, Community, Node, Project, User
from app.db.session import SessionLocal
from app.jobs.state_machine import JobStatus

RUN_ID = uuid.uuid4().hex[:8]
JOB_PARAMS = {
    "target_kind": "video",
    "target_value": "v",
    "max_comments": 500,
    "channel_video_count": 1,
}


def _completed_analysis(db, project: Project, *, created_at: datetime, seed: int) -> None:
    job = AnalysisJob(
        project=project,
        source_url="https://youtube.com/watch?v=loadtest",
        status=JobStatus.COMPLETED.value,
        params=JOB_PARAMS,
        progress=100,
    )
    db.add(job)
    db.flush()

    node_count = 150 + seed * 7
    community_count = 4
    analysis = Analysis(
        project_id=project.id,
        job_id=job.id,
        created_at=created_at,
        node_count=node_count,
        edge_count=node_count * 3,
        community_count=community_count,
        fetched_comment_count=node_count * 2,
        sentiment_summary={
            "distribution": {
                "positive": 40.0 + seed,
                "neutral": 35.0 - seed,
                "negative": 25.0,
            }
        },
    )
    db.add(analysis)
    db.flush()

    for i in range(30):
        db.add(
            Node(
                analysis_id=analysis.id,
                pseudonym=f"u{seed}-{i}",
                community_index=i % community_count,
                comment_count=i + 1,
                like_count=i * 3,
                engagement_score=float(i) / 30,
                pagerank=1.0 / (i + 1),
                betweenness=1.0 / (i + 2),
                influence_rank=i + 1,
                avg_sentiment=0.1,
            )
        )
    for c in range(community_count):
        db.add(
            Community(
                analysis_id=analysis.id,
                community_index=c,
                size=node_count // community_count,
                total_comments=50,
                total_likes=100,
                avg_sentiment=0.05,
                cohesion=0.4,
                density=0.3,
            )
        )


def _active_job(db, project: Project) -> None:
    job = AnalysisJob(
        project=project,
        source_url="https://youtube.com/watch?v=loadtest-active",
        status=JobStatus.ANALYZING.value,
        params=JOB_PARAMS,
        progress=60,
    )
    db.add(job)


def main() -> None:
    db = SessionLocal()
    try:
        user = User(
            email=f"loadtest-{RUN_ID}@example.com",
            username=f"loadtest{RUN_ID}",
            password_hash="unused",  # login isn't exercised; token is minted directly
            email_verified=True,
        )
        db.add(user)
        db.flush()

        primary = Project(name=f"Load test primary {RUN_ID}", user_id=user.id)
        db.add(primary)
        db.flush()

        base = datetime.now(UTC) - timedelta(days=30)
        analysis_ids: list[str] = []
        for i in range(6):
            _completed_analysis(db, primary, created_at=base + timedelta(days=i * 5), seed=i)
        db.flush()
        analysis_ids = [str(a.id) for a in primary.analyses]

        active_project_ids: list[str] = []
        for i in range(5):
            project = Project(name=f"Load test active {RUN_ID}-{i}", user_id=user.id)
            db.add(project)
            db.flush()
            _active_job(db, project)
            active_project_ids.append(str(project.id))

        db.commit()

        settings = get_settings()
        token = create_access_token(
            str(user.id), secret=settings.jwt_secret, expires_in=timedelta(hours=6)
        )

        print(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "token": token,
                    "primary_project_id": str(primary.id),
                    "analysis_id": analysis_ids[-1],
                    "active_project_ids": active_project_ids,
                },
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
