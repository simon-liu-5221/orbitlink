"""M2 — the analysis pipeline end to end against a real database.

FakeYouTube for ingestion, the lexicon stand-in for sentiment, real SQLAlchemy.
Run:  ``pytest -m integration``
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.sentiment import SentimentAnalyzer
from app.analysis.sentiment_lexicon import lexicon_predict
from app.core.config import Settings
from app.db.models import Analysis, AnalysisJob, Comment, Community, Node, Project, User
from app.ingest.youtube import YouTubeTarget
from app.jobs.state_machine import JobStatus
from app.services.analysis_service import (
    InvalidAnalysisRequestError,
    ProjectBusyError,
    SentimentModel,
    create_job,
    run_analysis,
)
from tests.support.youtube_fake import FakeYouTube, api_error, thread

pytestmark = pytest.mark.integration

_KEY = b"test-pseudonym-key"
_SETTINGS = Settings(_env_file=None)
_MODEL = SentimentModel(analyzer=SentimentAnalyzer(lexicon_predict), label="lexicon-standin")


def _project(db: Session) -> Project:
    project = Project(name="P", user=User(email=f"{uuid.uuid4()}@e.com"))
    db.add(project)
    db.flush()
    return project


def _conversation(fake: FakeYouTube, video: str = "vid00000001") -> None:
    """8 authors, a couple of reply chains — enough for community detection."""
    fake.comments[video] = [
        thread("c1", "UC_alice", "this video is amazing, best explanation, I love it"),
        thread(
            "c2",
            "UC_bob",
            "totally agree, great work",
            replies=[
                {"id": "r1", "author": "UC_carol", "text": "yes so helpful"},
                {"id": "r2", "author": "UC_alice", "text": "thanks everyone"},
            ],
        ),
        thread(
            "c3",
            "UC_dave",
            "honestly this was terrible and boring, waste of time",
            replies=[{"id": "r3", "author": "UC_erin", "text": "awful, I agree, disappointing"}],
        ),
        thread("c4", "UC_frank", "the pacing is fine, nothing special"),
        thread("c5", "UC_grace", "you are an idiot, shut up", likes=0),
        thread(
            "c6",
            "UC_alice",
            "following up on my earlier point",
            replies=[{"id": "r4", "author": "UC_bob", "text": "good point"}],
        ),
    ]


def test_video_analysis_completes_and_persists_everything(db_session: Session) -> None:
    project = _project(db_session)
    fake = FakeYouTube()
    _conversation(fake)
    job = AnalysisJob(
        project=project,
        source_url="https://youtu.be/vid00000001",
        params={
            "target_kind": "video",
            "target_value": "vid00000001",
            "max_comments": 5000,
            "channel_video_count": 10,
        },
    )
    db_session.add(job)
    db_session.flush()

    run_analysis(
        db_session, job.id, youtube_client=fake.client(), sentiment=_MODEL, pseudonym_key=_KEY
    )

    db_session.refresh(job)
    assert job.status == JobStatus.COMPLETED.value
    assert job.progress == 100
    assert job.error_code is None
    assert job.finished_at is not None

    analysis = db_session.scalar(select(Analysis).where(Analysis.job_id == job.id))
    assert analysis is not None
    assert analysis.insufficient_data is False
    assert analysis.node_count >= 5
    assert analysis.community_count >= 1
    assert analysis.fetched_comment_count == 10  # 6 top-level + 4 replies
    assert analysis.sentiment_summary["model"] == "lexicon-standin"

    nodes = db_session.scalars(select(Node).where(Node.analysis_id == analysis.id)).all()
    communities = db_session.scalars(
        select(Community).where(Community.analysis_id == analysis.id)
    ).all()
    comments = db_session.scalars(select(Comment).where(Comment.analysis_id == analysis.id)).all()
    assert len(nodes) == analysis.node_count
    assert len(communities) == analysis.community_count
    assert len(comments) == 10

    # data-ethics: no raw YouTube channel id anywhere
    assert all(not n.pseudonym.startswith("UC_") for n in nodes)
    assert all(not c.author_pseudonym.startswith("UC_") for c in comments)
    assert {n.influence_rank for n in nodes} >= {1}
    assert any(c.sentiment_label == "positive" for c in comments)
    assert any(c.sentiment_label == "negative" for c in comments)


def test_too_few_comments_completes_with_insufficient_data(db_session: Session) -> None:
    project = _project(db_session)
    fake = FakeYouTube()
    fake.comments["v"] = [thread("c1", "UC_a", "hi"), thread("c2", "UC_b", "yo")]
    job = AnalysisJob(
        project=project,
        source_url="u",
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 5000,
            "channel_video_count": 10,
        },
    )
    db_session.add(job)
    db_session.flush()

    run_analysis(
        db_session, job.id, youtube_client=fake.client(), sentiment=_MODEL, pseudonym_key=_KEY
    )

    db_session.refresh(job)
    assert job.status == JobStatus.COMPLETED.value
    analysis = db_session.scalar(select(Analysis).where(Analysis.job_id == job.id))
    assert analysis is not None
    assert analysis.insufficient_data is True
    assert analysis.modularity is None


def test_quota_exceeded_fails_the_job(db_session: Session) -> None:
    project = _project(db_session)
    fake = FakeYouTube()
    fake.video_error["v"] = api_error(403, "quotaExceeded")
    job = AnalysisJob(
        project=project,
        source_url="u",
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 5000,
            "channel_video_count": 10,
        },
    )
    db_session.add(job)
    db_session.flush()

    run_analysis(
        db_session, job.id, youtube_client=fake.client(), sentiment=_MODEL, pseudonym_key=_KEY
    )

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "QUOTA_EXCEEDED"
    assert db_session.scalar(select(Analysis).where(Analysis.job_id == job.id)) is None


def test_cancellation_is_honoured_mid_run(db_session: Session) -> None:
    project = _project(db_session)
    fake = FakeYouTube()
    _conversation(fake, "v")

    class Cancelling:
        def fetch(self, *args: object, **kwargs: object) -> object:
            result = fake.client().fetch(YouTubeTarget("video", "v"))
            job_row = db_session.get(AnalysisJob, job.id)
            assert job_row is not None
            job_row.status = JobStatus.CANCELLED.value
            db_session.flush()
            return result

    job = AnalysisJob(
        project=project,
        source_url="u",
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 5000,
            "channel_video_count": 10,
        },
    )
    db_session.add(job)
    db_session.flush()

    run_analysis(
        db_session, job.id, youtube_client=Cancelling(), sentiment=_MODEL, pseudonym_key=_KEY
    )  # type: ignore[arg-type]

    db_session.refresh(job)
    assert job.status == JobStatus.CANCELLED.value
    assert db_session.scalar(select(Analysis).where(Analysis.job_id == job.id)) is None


def test_pipeline_error_fails_the_job_not_a_bare_500(db_session: Session) -> None:
    project = _project(db_session)
    fake = FakeYouTube()
    _conversation(fake, "v")

    def boom(_texts: object) -> list[object]:
        raise RuntimeError("model exploded")

    broken = SentimentModel(analyzer=SentimentAnalyzer(boom), label="broken")  # type: ignore[arg-type]
    job = AnalysisJob(
        project=project,
        source_url="u",
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 5000,
            "channel_video_count": 10,
        },
    )
    db_session.add(job)
    db_session.flush()

    run_analysis(
        db_session, job.id, youtube_client=fake.client(), sentiment=broken, pseudonym_key=_KEY
    )

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error_code == "ANALYSIS_ERROR"


def test_run_analysis_on_missing_job_raises() -> None:
    from app.services.analysis_service import AnalysisServiceError
    from app.services.analysis_service import run_analysis as _run

    class _NoSession:
        def get(self, *_a: object, **_k: object) -> None:
            return None

    with pytest.raises(AnalysisServiceError, match="not found"):
        _run(_NoSession(), uuid.uuid4(), youtube_client=None, sentiment=_MODEL, pseudonym_key=_KEY)  # type: ignore[arg-type]


def test_run_analysis_is_a_noop_for_a_terminal_job(db_session: Session) -> None:
    project = _project(db_session)
    job = AnalysisJob(
        project=project,
        source_url="u",
        status=JobStatus.COMPLETED.value,
        params={
            "target_kind": "video",
            "target_value": "v",
            "max_comments": 1,
            "channel_video_count": 1,
        },
    )
    db_session.add(job)
    db_session.flush()
    result = run_analysis(
        db_session, job.id, youtube_client=None, sentiment=_MODEL, pseudonym_key=_KEY
    )  # type: ignore[arg-type]
    assert result.status == JobStatus.COMPLETED.value


def test_create_job_rejects_zero_max_comments(db_session: Session) -> None:
    project = _project(db_session)
    with pytest.raises(InvalidAnalysisRequestError, match="positive"):
        create_job(
            db_session,
            project_id=project.id,
            source_url="https://youtu.be/dQw4w9WgXcQ",
            settings=_SETTINGS,
            overrides={"max_comments": 0},
        )


def test_create_job_rejects_bad_url(db_session: Session) -> None:
    project = _project(db_session)
    with pytest.raises(InvalidAnalysisRequestError) as exc:
        create_job(
            db_session, project_id=project.id, source_url="https://vimeo.com/1", settings=_SETTINGS
        )
    assert exc.value.code == "INVALID_URL"


def test_create_job_rejects_over_the_comment_cap(db_session: Session) -> None:
    project = _project(db_session)
    with pytest.raises(InvalidAnalysisRequestError) as exc:
        create_job(
            db_session,
            project_id=project.id,
            source_url="https://youtu.be/dQw4w9WgXcQ",
            settings=_SETTINGS,
            overrides={"max_comments": 999_999},
        )
    assert exc.value.code == "COMMENT_CAP_EXCEEDED"


def test_create_job_rejects_a_second_live_job(db_session: Session) -> None:
    project = _project(db_session)
    create_job(
        db_session,
        project_id=project.id,
        source_url="https://youtu.be/dQw4w9WgXcQ",
        settings=_SETTINGS,
    )
    with pytest.raises(ProjectBusyError):
        create_job(
            db_session,
            project_id=project.id,
            source_url="https://youtu.be/dQw4w9WgXcQ",
            settings=_SETTINGS,
        )


def test_create_job_stores_a_queued_row(db_session: Session) -> None:
    project = _project(db_session)
    job = create_job(
        db_session,
        project_id=project.id,
        source_url="https://www.youtube.com/@creator",
        settings=_SETTINGS,
    )
    assert job.status == JobStatus.QUEUED.value
    assert job.params["target_kind"] == "handle"
    assert job.params["target_value"] == "creator"
    assert job.params["max_comments"] == _SETTINGS.analysis_default_max_comments
