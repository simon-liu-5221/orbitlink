"""``analysis_jobs`` — the persisted job state machine (ADR-0002, spec AN-05)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.jobs.state_machine import JobStatus

if TYPE_CHECKING:
    from app.db.models.analysis import Analysis
    from app.db.models.project import Project


class AnalysisJob(Base, TimestampMixin):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED.value, index=True)
    progress: Mapped[int] = mapped_column(default=0)

    #: The YouTube URL the user submitted (kept for display / retry).
    source_url: Mapped[str] = mapped_column(String(2048))
    #: Analysis parameters snapshot: comment cap, channel video count, etc.
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    #: RQ job id, for cancellation and orphan detection.
    rq_job_id: Mapped[str | None] = mapped_column(String(64), default=None)
    #: Last worker heartbeat; a job with no heartbeat for 30 min is reaped.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    project: Mapped[Project] = relationship(back_populates="jobs")
    analysis: Mapped[Analysis | None] = relationship(back_populates="job", uselist=False)

    @property
    def status_enum(self) -> JobStatus:
        return JobStatus(self.status)

    @property
    def is_terminal(self) -> bool:
        from app.jobs.state_machine import TERMINAL

        return self.status_enum in TERMINAL
