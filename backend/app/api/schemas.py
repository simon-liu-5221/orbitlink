"""Request / response models for the analysis API (PR-01)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

if TYPE_CHECKING:
    from app.db.models import AnalysisJob


class ORMModel(BaseModel):
    """Response models read straight off SQLAlchemy rows."""

    model_config = ConfigDict(from_attributes=True)


# --- auth (GU-01 / PR-02) ---------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    remember_me: bool = False


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    #: Strength is checked in the service layer so every unmet rule is reported
    #: at once (PR-03 AC-6), not just the first Pydantic violation.
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    username: str
    email_verified: bool
    subscription_plan: str
    trial_ends_at: datetime | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    #: Seconds until the access token expires.
    expires_in: int
    user: UserOut


class MessageResponse(BaseModel):
    message: str


# --- projects ----------------------------------------------------------

#: A project name with surrounding whitespace trimmed; empty after the trim
#: is rejected before it reaches the service layer (PR-07 AC-2).
ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ProjectCreate(BaseModel):
    name: ProjectName


class ProjectRename(BaseModel):
    name: ProjectName


class ProjectOut(ORMModel):
    id: uuid.UUID
    name: str
    archived_at: datetime | None
    created_at: datetime


# --- analyses --------------------------------------------------------


class AnalysisCreate(BaseModel):
    source_url: str = Field(min_length=1, max_length=2048)
    max_comments: int | None = Field(default=None, ge=1)
    channel_video_count: int | None = Field(default=None, ge=1)


class JobAccepted(BaseModel):
    job_id: uuid.UUID
    status: str


class JobStatusOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    progress: int
    error_code: str | None
    error_message: str | None
    analysis_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: AnalysisJob) -> JobStatusOut:
        return cls(
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


# --- results --------------------------------------------------------


class CommunityOut(BaseModel):
    community_index: int
    size: int
    total_comments: int
    total_likes: int
    avg_sentiment: float | None
    cohesion: float
    density: float
    top_influencers: list[str]
    bridge_users: list[str]


class NodeOut(BaseModel):
    pseudonym: str
    community_index: int | None
    comment_count: int
    like_count: int
    replies_received: int
    engagement_score: float
    engagement_breakdown: dict[str, float]
    pagerank: float
    betweenness: float
    influence_rank: int | None
    avg_sentiment: float | None


class AnalysisOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    created_at: datetime
    insufficient_data: bool
    weak_structure: bool
    approximated: bool
    modularity: float | None
    resolution_used: float | None
    node_count: int
    edge_count: int
    community_count: int
    fetched_comment_count: int
    period_start: datetime | None
    period_end: datetime | None
    sentiment_summary: dict[str, Any]
    communities: list[CommunityOut]
    #: Top participants by influence rank (not the full node list — see /graph, PR-10).
    top_influencers: list[NodeOut]
    #: Top participants by engagement score.
    top_engaged: list[NodeOut]


# --- network graph (PR-10) --------------------------------------------


class GraphEdgeOut(BaseModel):
    source: str
    target: str
    weight: int


class AnalysisGraphOut(BaseModel):
    #: Every node, not just the top 20 (unlike AnalysisOut) — ordered by
    #: pagerank descending so a frontend that samples top-N needs no resort.
    nodes: list[NodeOut]
    edges: list[GraphEdgeOut]
    node_count: int
    edge_count: int
