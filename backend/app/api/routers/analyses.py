"""Analysis endpoints (spec PR-01).

POST /api/v1/projects/{id}/analyses   -> 202 { job_id }
GET  /api/v1/jobs/{job_id}            -> status + progress (poll every 2s)
POST /api/v1/jobs/{job_id}/cancel     -> mark cancelled
GET  /api/v1/analyses/{analysis_id}   -> summary + communities + top participants
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentUser, DbSession, rate_limit_analyses
from app.api.schemas import (
    AnalysisCreate,
    AnalysisOut,
    CommunityOut,
    JobAccepted,
    JobStatusOut,
    NodeOut,
)
from app.db.models import Analysis, AnalysisJob, Community, Node, Project, User
from app.jobs.queue import get_queue
from app.jobs.state_machine import TERMINAL, JobStatus, assert_transition
from app.jobs.tasks import run_analysis_job
from app.services.analysis_service import (
    InvalidAnalysisRequestError,
    ProjectBusyError,
    create_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

_TOP_N = 20


def _owned_project(db: DbSession, project_id: uuid.UUID, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        # same response whether it doesn't exist or isn't theirs (PR-01 AC-4)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "project not found or not yours")
    return project


@router.post(
    "/projects/{project_id}/analyses",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobAccepted,
    dependencies=[Depends(rate_limit_analyses)],
)
def start_analysis(
    project_id: uuid.UUID,
    body: AnalysisCreate,
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
) -> JobAccepted:
    _owned_project(db, project_id, user)

    overrides: dict[str, int] = {}
    if body.max_comments is not None:
        overrides["max_comments"] = body.max_comments
    if body.channel_video_count is not None:
        overrides["channel_video_count"] = body.channel_video_count

    try:
        job = create_job(
            db,
            project_id=project_id,
            source_url=body.source_url,
            settings=settings,
            overrides=overrides,
        )
    except InvalidAnalysisRequestError as exc:
        raise HTTPException(
            422,
            detail={"error_code": exc.code, "message": str(exc)},
        ) from exc
    except ProjectBusyError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"error_code": "PROJECT_BUSY", "message": str(exc), "job_id": str(exc.job_id)},
        ) from exc

    db.commit()  # durable before the worker can pick it up

    try:
        rq_job = get_queue().enqueue(run_analysis_job, str(job.id))
        job.rq_job_id = rq_job.id
        db.commit()
    except Exception as exc:
        logger.exception("failed to enqueue analysis job %s", job.id)
        job.status = JobStatus.FAILED.value
        job.error_code = "ENQUEUE_FAILED"
        job.error_message = str(exc)[:2000]
        db.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "could not queue the analysis, try again"
        ) from exc

    return JobAccepted(job_id=job.id, status=job.status)


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def get_job(job_id: uuid.UUID, db: DbSession, user: CurrentUser) -> JobStatusOut:
    job = _owned_job(db, job_id, user)
    return _job_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobStatusOut)
def cancel_job(job_id: uuid.UUID, db: DbSession, user: CurrentUser) -> JobStatusOut:
    job = _owned_job(db, job_id, user)
    if job.status_enum in TERMINAL:
        raise HTTPException(status.HTTP_409_CONFLICT, f"job already {job.status}")
    assert_transition(job.status_enum, JobStatus.CANCELLED)
    job.status = JobStatus.CANCELLED.value
    if job.rq_job_id:
        try:
            get_queue().remove(job.rq_job_id)
        except Exception:
            logger.warning("could not remove rq job %s", job.rq_job_id)
    db.commit()
    return _job_out(job)


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: uuid.UUID, db: DbSession, user: CurrentUser) -> AnalysisOut:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "analysis not found")

    communities = db.scalars(
        select(Community)
        .where(Community.analysis_id == analysis.id)
        .order_by(Community.community_index)
    ).all()
    influencers = db.scalars(
        select(Node)
        .where(Node.analysis_id == analysis.id, Node.influence_rank.is_not(None))
        .order_by(Node.influence_rank)
        .limit(_TOP_N)
    ).all()
    engaged = db.scalars(
        select(Node)
        .where(Node.analysis_id == analysis.id)
        .order_by(Node.engagement_score.desc())
        .limit(_TOP_N)
    ).all()

    return AnalysisOut(
        id=analysis.id,
        project_id=analysis.project_id,
        job_id=analysis.job_id,
        created_at=analysis.created_at,
        insufficient_data=analysis.insufficient_data,
        weak_structure=analysis.weak_structure,
        approximated=analysis.approximated,
        modularity=analysis.modularity,
        resolution_used=analysis.resolution_used,
        node_count=analysis.node_count,
        edge_count=analysis.edge_count,
        community_count=analysis.community_count,
        fetched_comment_count=analysis.fetched_comment_count,
        period_start=analysis.period_start,
        period_end=analysis.period_end,
        sentiment_summary=analysis.sentiment_summary,
        communities=[_community_out(c) for c in communities],
        top_influencers=[_node_out(n) for n in influencers],
        top_engaged=[_node_out(n) for n in engaged],
    )


# --- mappers ---------------------------------------------------------


def _owned_job(db: DbSession, job_id: uuid.UUID, user: User) -> AnalysisJob:
    job = db.get(AnalysisJob, job_id)
    if job is None or job.project.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job


def _job_out(job: AnalysisJob) -> JobStatusOut:
    return JobStatusOut(
        id=job.id,
        project_id=job.project_id,
        status=job.status,
        progress=job.progress,
        error_code=job.error_code,
        error_message=job.error_message,
        analysis_id=job.analysis.id if job.analysis else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _community_out(c: Community) -> CommunityOut:
    return CommunityOut(
        community_index=c.community_index,
        size=c.size,
        total_comments=c.total_comments,
        total_likes=c.total_likes,
        avg_sentiment=c.avg_sentiment,
        cohesion=c.cohesion,
        density=c.density,
        top_influencers=list(c.top_influencers),
        bridge_users=list(c.bridge_users),
    )


def _node_out(n: Node) -> NodeOut:
    return NodeOut(
        pseudonym=n.pseudonym,
        community_index=n.community_index,
        comment_count=n.comment_count,
        like_count=n.like_count,
        replies_received=n.replies_received,
        engagement_score=n.engagement_score,
        engagement_breakdown=dict(n.engagement_breakdown),
        pagerank=n.pagerank,
        betweenness=n.betweenness,
        influence_rank=n.influence_rank,
        avg_sentiment=n.avg_sentiment,
    )
