"""Persisted analysis output: ``analyses`` + ``nodes`` / ``communities`` /
``comments`` (+ optional ``raw_comments``).

The analysis layer (M1) produces dataclasses; the service layer (M2, PR-3) maps
them onto these rows in the ``persisting`` stage.

Per ``docs/data-ethics.md``: author identifiers are HMAC pseudonyms, raw comment
text is deleted after sentiment inference. ``raw_comments`` exists for the
opt-in retention path (decision E1: schema only for now, nothing writes to it).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.job import AnalysisJob
    from app.db.models.project import Project


class Analysis(Base, TimestampMixin):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True
    )

    insufficient_data: Mapped[bool] = mapped_column(Boolean, default=False)
    weak_structure: Mapped[bool] = mapped_column(Boolean, default=False)
    approximated: Mapped[bool] = mapped_column(Boolean, default=False)

    modularity: Mapped[float | None] = mapped_column(Float, default=None)
    resolution_used: Mapped[float | None] = mapped_column(Float, default=None)

    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)
    community_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_comment_count: Mapped[int] = mapped_column(Integer, default=0)

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    #: Aggregate sentiment (distribution / trend / toxic_ratio / failed_ratio).
    sentiment_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    #: Parameters this analysis actually ran with.
    params_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    project: Mapped[Project] = relationship(back_populates="analyses")
    job: Mapped[AnalysisJob] = relationship(back_populates="analysis")
    nodes: Mapped[list[Node]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    communities: Mapped[list[Community]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (UniqueConstraint("analysis_id", "pseudonym"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    pseudonym: Mapped[str] = mapped_column(String(64), index=True)
    community_index: Mapped[int | None] = mapped_column(Integer, default=None)

    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    replies_received: Mapped[int] = mapped_column(Integer, default=0)
    active_days: Mapped[int] = mapped_column(Integer, default=0)

    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    pagerank: Mapped[float] = mapped_column(Float, default=0.0)
    betweenness: Mapped[float] = mapped_column(Float, default=0.0)
    influence_rank: Mapped[int | None] = mapped_column(Integer, default=None)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, default=None)

    analysis: Mapped[Analysis] = relationship(back_populates="nodes")


class Community(Base):
    __tablename__ = "communities"
    __table_args__ = (UniqueConstraint("analysis_id", "community_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    community_index: Mapped[int] = mapped_column(Integer)

    size: Mapped[int] = mapped_column(Integer, default=0)
    total_comments: Mapped[int] = mapped_column(Integer, default=0)
    total_likes: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float | None] = mapped_column(Float, default=None)
    cohesion: Mapped[float] = mapped_column(Float, default=0.0)
    density: Mapped[float] = mapped_column(Float, default=0.0)
    top_influencers: Mapped[list[str]] = mapped_column(JSONB, default=list)
    bridge_users: Mapped[list[str]] = mapped_column(JSONB, default=list)

    analysis: Mapped[Analysis] = relationship(back_populates="communities")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    #: HMAC of the YouTube comment id — a stable reference without storing the id.
    external_ref: Mapped[str] = mapped_column(String(64))
    author_pseudonym: Mapped[str] = mapped_column(String(64), index=True)
    parent_author_pseudonym: Mapped[str | None] = mapped_column(String(64), default=None)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    text_length: Mapped[int] = mapped_column(Integer, default=0)

    sentiment_label: Mapped[str | None] = mapped_column(String(16), default=None)
    sentiment_score: Mapped[float | None] = mapped_column(Float, default=None)
    toxicity: Mapped[float | None] = mapped_column(Float, default=None)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False)

    analysis: Mapped[Analysis] = relationship(back_populates="comments")
    raw: Mapped[RawComment | None] = relationship(
        back_populates="comment", uselist=False, cascade="all, delete-orphan"
    )


class RawComment(Base):
    """Original comment text — only written when the user opts into retention
    (decision E1: schema only for M2). Purged after ``expires_at`` by a
    scheduled job (30-day TTL, ``docs/data-ethics.md``).
    """

    __tablename__ = "raw_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), unique=True, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    comment: Mapped[Comment] = relationship(back_populates="raw")
