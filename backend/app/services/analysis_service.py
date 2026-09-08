"""Analysis orchestration — the ``analyzing`` pipeline of ADR-0002 / PR-01.

``create_job`` validates a request and inserts a ``queued`` row. ``run_analysis``
drives one job through fetching -> building_graph -> analyzing -> persisting,
updating status/progress/heartbeat at every stage and stopping cleanly on
cancellation. It never lets an exception escape as a bare 500 — everything maps
to a ``failed`` job with an ``error_code``.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.communities import detect_communities
from app.analysis.engagement import score_engagement
from app.analysis.graph_builder import build_interaction_graph
from app.analysis.influence import InfluenceResult, rank_influencers
from app.analysis.sentiment import SentimentAnalyzer
from app.analysis.types import EngagementResult, SentimentResult
from app.core.config import Settings
from app.db.models import Analysis, AnalysisJob, Comment, Community, Node
from app.ingest.pseudonym import pseudonymize
from app.ingest.urls import InvalidYouTubeURLError, YouTubeTarget, parse_youtube_url
from app.ingest.youtube import RawComment, YouTubeClient, YouTubeError
from app.jobs.state_machine import TERMINAL, JobStatus, assert_transition, clamp_progress

logger = logging.getLogger(__name__)

_FRAME_COLUMNS = ["comment_id", "author_id", "parent_id", "text", "like_count", "published_at"]


class AnalysisServiceError(RuntimeError):
    pass


class InvalidAnalysisRequestError(AnalysisServiceError):
    def __init__(self, message: str, *, code: str = "INVALID_REQUEST") -> None:
        super().__init__(message)
        self.code = code


class ProjectBusyError(AnalysisServiceError):
    def __init__(self, job_id: uuid.UUID) -> None:
        super().__init__(f"project already has analysis job {job_id} in progress")
        self.job_id = job_id


class JobCancelledError(AnalysisServiceError):
    pass


@dataclass(frozen=True)
class SentimentModel:
    analyzer: SentimentAnalyzer
    label: str


# --- create -------------------------------------------------------------


def create_job(
    session: Session,
    *,
    project_id: uuid.UUID,
    source_url: str,
    settings: Settings,
    overrides: Mapping[str, int] | None = None,
) -> AnalysisJob:
    overrides = overrides or {}
    try:
        target = parse_youtube_url(source_url)
    except InvalidYouTubeURLError as exc:
        raise InvalidAnalysisRequestError(str(exc), code="INVALID_URL") from exc

    max_comments = int(overrides.get("max_comments", settings.analysis_default_max_comments))
    if max_comments < 1:
        raise InvalidAnalysisRequestError("max_comments must be positive", code="INVALID_REQUEST")
    if max_comments > settings.analysis_max_comments_cap:
        raise InvalidAnalysisRequestError(
            f"max_comments {max_comments} exceeds the {settings.analysis_max_comments_cap} cap",
            code="COMMENT_CAP_EXCEEDED",
        )
    video_count = int(overrides.get("channel_video_count", settings.analysis_channel_video_count))

    live = session.scalar(
        select(AnalysisJob)
        .where(
            AnalysisJob.project_id == project_id,
            AnalysisJob.status.notin_([status.value for status in TERMINAL]),
        )
        .limit(1)
    )
    if live is not None:
        raise ProjectBusyError(live.id)

    job = AnalysisJob(
        project_id=project_id,
        source_url=source_url,
        status=JobStatus.QUEUED.value,
        params={
            "target_kind": target.kind,
            "target_value": target.value,
            "max_comments": max_comments,
            "channel_video_count": video_count,
        },
    )
    session.add(job)
    session.flush()
    return job


# --- run --------------------------------------------------------------


def run_analysis(
    session: Session,
    job_id: uuid.UUID,
    *,
    youtube_client: YouTubeClient,
    sentiment: SentimentModel,
    pseudonym_key: bytes,
) -> AnalysisJob:
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise AnalysisServiceError(f"job {job_id} not found")
    if job.status_enum in TERMINAL:
        return job

    job.started_at = datetime.now(UTC)
    target = YouTubeTarget(job.params["target_kind"], job.params["target_value"])
    max_comments = int(job.params["max_comments"])
    video_count = int(job.params["channel_video_count"])

    try:
        _advance(session, job, JobStatus.FETCHING)
        fetch = youtube_client.fetch(
            target, max_comments=max_comments, channel_video_count=video_count
        )
        _guard_cancelled(session, job)

        _advance(session, job, JobStatus.BUILDING_GRAPH)
        frame = _to_frame(fetch.comments, pseudonym_key)
        graph = build_interaction_graph(frame)
        _guard_cancelled(session, job)

        _advance(session, job, JobStatus.ANALYZING)
        communities = detect_communities(graph)
        influence = (
            rank_influencers(graph)
            if graph.number_of_nodes()
            else InfluenceResult(ranking=[], approximated=False)
        )
        engagement = score_engagement(graph) if graph.number_of_nodes() else None
        sentiment_result = sentiment.analyzer.analyze(
            _sentiment_frame(frame, communities.node_communities)
        )
        _guard_cancelled(session, job)

        _advance(session, job, JobStatus.PERSISTING)
        _persist(
            session,
            job,
            fetch_comment_count=len(fetch.comments),
            frame=frame,
            graph=graph,
            communities=communities,
            influence=influence,
            engagement=engagement,
            sentiment_result=sentiment_result,
            model_label=sentiment.label,
        )

        _advance(session, job, JobStatus.COMPLETED)
        job.finished_at = datetime.now(UTC)
    except JobCancelledError:
        job.finished_at = datetime.now(UTC)
    except YouTubeError as exc:
        _fail(session, job, exc.error_code, str(exc))
    except Exception as exc:
        logger.exception("analysis job %s failed", job_id)
        _fail(session, job, "ANALYSIS_ERROR", str(exc))

    session.flush()
    return job


# --- stage helpers -------------------------------------------------


def _advance(session: Session, job: AnalysisJob, target: JobStatus) -> None:
    assert_transition(job.status_enum, target)
    job.status = target.value
    job.progress = clamp_progress(job.progress, target)
    job.heartbeat_at = datetime.now(UTC)
    session.flush()


def _guard_cancelled(session: Session, job: AnalysisJob) -> None:
    session.refresh(job, ["status"])
    if job.status_enum is JobStatus.CANCELLED:
        raise JobCancelledError(str(job.id))


def _fail(session: Session, job: AnalysisJob, code: str, message: str) -> None:
    if job.status_enum in TERMINAL:
        return
    assert_transition(job.status_enum, JobStatus.FAILED)
    job.status = JobStatus.FAILED.value
    job.error_code = code
    job.error_message = message[:2000]
    job.finished_at = datetime.now(UTC)
    session.flush()


# --- data shaping ------------------------------------------------


def _to_frame(comments: list[RawComment], key: bytes) -> pd.DataFrame:
    id_map = {c.comment_id: pseudonymize(c.comment_id, key=key) for c in comments}
    rows = [
        {
            "comment_id": id_map[c.comment_id],
            "author_id": pseudonymize(c.author_channel_id, key=key),
            "parent_id": id_map.get(c.parent_id) if c.parent_id else None,
            "text": c.text,
            "like_count": c.like_count,
            "published_at": c.published_at,
        }
        for c in comments
    ]
    return pd.DataFrame(rows, columns=_FRAME_COLUMNS)


def _sentiment_frame(frame: pd.DataFrame, node_communities: dict[str, int]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["comment_id", "text", "published_at", "community_id"])
    return pd.DataFrame(
        {
            "comment_id": frame["comment_id"],
            "text": frame["text"],
            "published_at": frame["published_at"],
            "community_id": frame["author_id"].map(node_communities),
        }
    )


# --- persistence ------------------------------------------------


def _persist(
    session: Session,
    job: AnalysisJob,
    *,
    fetch_comment_count: int,
    frame: pd.DataFrame,
    graph: Any,
    communities: Any,
    influence: InfluenceResult,
    engagement: EngagementResult | None,
    sentiment_result: SentimentResult,
    model_label: str,
) -> Analysis:
    analysis = Analysis(
        project_id=job.project_id,
        job_id=job.id,
        insufficient_data=communities.insufficient_data,
        weak_structure=communities.weak_structure,
        approximated=bool(communities.approximated or influence.approximated),
        modularity=None if communities.insufficient_data else communities.modularity,
        resolution_used=None if communities.insufficient_data else communities.resolution_used,
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        community_count=len(communities.communities),
        fetched_comment_count=fetch_comment_count,
        period_start=graph.graph.get("start"),
        period_end=graph.graph.get("end"),
        sentiment_summary=_sentiment_summary(sentiment_result, model_label),
        params_snapshot=dict(job.params),
    )
    session.add(analysis)
    session.flush()

    engagement_by_node = {n.node_id: n for n in engagement.rankings} if engagement else {}
    influence_by_node = {i.node_id: i for i in influence.ranking}
    node_sentiment = _mean_sentiment_by_author(frame, sentiment_result)

    for node_id, data in graph.nodes(data=True):
        eng = engagement_by_node.get(node_id)
        inf = influence_by_node.get(node_id)
        session.add(
            Node(
                analysis_id=analysis.id,
                pseudonym=str(node_id),
                community_index=communities.node_communities.get(node_id),
                comment_count=int(data.get("comment_count", 0)),
                like_count=int(data.get("like_count", 0)),
                replies_received=int(data.get("replies_received", 0)),
                active_days=int(data.get("active_days", 0)),
                engagement_score=float(eng.score) if eng else 0.0,
                engagement_breakdown=dict(eng.breakdown) if eng else {},
                pagerank=float(inf.pagerank) if inf else 0.0,
                betweenness=float(inf.betweenness) if inf else 0.0,
                influence_rank=inf.rank if inf else None,
                avg_sentiment=node_sentiment.get(node_id),
            )
        )

    for metrics in communities.communities:
        session.add(
            Community(
                analysis_id=analysis.id,
                community_index=metrics.community_id,
                size=metrics.size,
                total_comments=metrics.total_comments,
                total_likes=metrics.total_likes,
                avg_sentiment=sentiment_result.by_community.get(metrics.community_id),
                cohesion=metrics.cohesion,
                density=metrics.density,
                top_influencers=list(metrics.top_influencers),
                bridge_users=list(metrics.bridge_users),
            )
        )

    _persist_comments(session, analysis.id, frame, sentiment_result)
    session.flush()
    return analysis


def _persist_comments(
    session: Session, analysis_id: uuid.UUID, frame: pd.DataFrame, sentiment_result: SentimentResult
) -> None:
    if frame.empty:
        return
    author_by_comment = dict(zip(frame["comment_id"], frame["author_id"], strict=True))
    per_comment = {c.comment_id: c for c in sentiment_result.comments}
    for row in frame.to_dict("records"):
        result = per_comment.get(row["comment_id"])
        parent_id = row["parent_id"]
        parent = author_by_comment.get(parent_id) if parent_id else None
        published = row["published_at"]
        session.add(
            Comment(
                analysis_id=analysis_id,
                external_ref=str(row["comment_id"]),
                author_pseudonym=str(row["author_id"]),
                parent_author_pseudonym=parent,
                published_at=None if published is None or pd.isna(published) else published,
                like_count=int(row["like_count"]),
                text_length=len(str(row["text"])),
                sentiment_label=result.label if result else None,
                sentiment_score=result.score if result else None,
                toxicity=result.toxicity if result else None,
                skipped=bool(result.skipped) if result else False,
                failed=bool(result.failed) if result else False,
            )
        )


def _mean_sentiment_by_author(
    frame: pd.DataFrame, sentiment_result: SentimentResult
) -> dict[str, float]:
    if frame.empty:
        return {}
    scores = {c.comment_id: c.score for c in sentiment_result.comments if c.score is not None}
    author_of = dict(zip(frame["comment_id"], frame["author_id"], strict=True))
    buckets: dict[str, list[float]] = {}
    for comment_id, score in scores.items():
        author = author_of.get(comment_id)
        if author is not None:
            buckets.setdefault(author, []).append(score)
    return {author: round(sum(v) / len(v), 6) for author, v in buckets.items()}


def _sentiment_summary(result: SentimentResult, model_label: str) -> dict[str, Any]:
    return {
        "model": model_label,
        "distribution": result.distribution,
        "trend_bucket": result.trend_bucket,
        "trend": [
            {
                "bucket_start": p.bucket_start.isoformat(),
                "mean_score": p.mean_score,
                "count": p.count,
            }
            for p in result.trend
        ],
        "by_community": {str(k): v for k, v in result.by_community.items()},
        "toxic_ratio": result.toxic_ratio,
        "skipped_count": result.skipped_count,
        "failed_ratio": result.failed_ratio,
        "truncated_ratio": result.truncated_ratio,
    }
