"""Project model — a container for analyses of one channel/video over time.

Full project CRUD (rename / archive / search) is spec PR-07 (M3); M2 needs only
enough to hang analyses off.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.analysis import Analysis
    from app.db.models.job import AnalysisJob
    from app.db.models.user import User

#: Seeded dev project (migration 0002), owned by the dev-placeholder user.
DEV_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    user: Mapped[User] = relationship(back_populates="projects")
    jobs: Mapped[list[AnalysisJob]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
