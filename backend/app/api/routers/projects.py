"""Project endpoints (spec PR-07).

Create / list / search / rename / archive / unarchive / delete, plus the job
history the frontend project-detail page renders.

Every route that names a project id goes through :func:`_owned_project`, which
answers 403 identically whether the project belongs to someone else or does not
exist — user A must not be able to probe user B's ids (NFR SEC-02).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import JobStatusOut, ProjectCreate, ProjectOut, ProjectRename
from app.db.models import AnalysisJob, Project, User
from app.jobs.state_machine import TERMINAL

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

_NOT_FOUND = HTTPException(status.HTTP_403_FORBIDDEN, "project not found or not yours")


def _owned_project(db: DbSession, project_id: uuid.UUID, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise _NOT_FOUND
    return project


def _escape_like(term: str) -> str:
    """Neutralise the caller's ``%`` / ``_`` so a search stays a literal search."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
def create_project(body: ProjectCreate, db: DbSession, user: CurrentUser) -> Project:
    project = Project(name=body.name, user_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: DbSession,
    user: CurrentUser,
    q: Annotated[str | None, Query(max_length=200)] = None,
    include_archived: bool = False,
) -> list[Project]:
    stmt = select(Project).where(Project.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    if q and q.strip():
        stmt = stmt.where(Project.name.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))
    return list(db.scalars(stmt.order_by(Project.created_at.desc())).all())


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    return _owned_project(db, project_id, user)


@router.patch("/{project_id}", response_model=ProjectOut)
def rename_project(
    project_id: uuid.UUID, body: ProjectRename, db: DbSession, user: CurrentUser
) -> Project:
    project = _owned_project(db, project_id, user)
    project.name = body.name
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = _owned_project(db, project_id, user)
    if project.archived_at is None:  # idempotent — a second call is a no-op
        project.archived_at = datetime.now(UTC)
        db.commit()
        db.refresh(project)
    return project


@router.post("/{project_id}/unarchive", response_model=ProjectOut)
def unarchive_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = _owned_project(db, project_id, user)
    if project.archived_at is not None:
        project.archived_at = None
        db.commit()
        db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    project = _owned_project(db, project_id, user)
    live = db.scalar(
        select(AnalysisJob)
        .where(
            AnalysisJob.project_id == project.id,
            AnalysisJob.status.notin_([s.value for s in TERMINAL]),
        )
        .limit(1)
    )
    if live is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "error_code": "PROJECT_BUSY",
                "message": "wait for the running analysis to finish, or cancel it first",
                "job_id": str(live.id),
            },
        )
    db.delete(project)
    db.commit()


@router.get("/{project_id}/jobs", response_model=list[JobStatusOut])
def list_project_jobs(
    project_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> list[JobStatusOut]:
    project = _owned_project(db, project_id, user)
    jobs = db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project.id)
        .order_by(AnalysisJob.created_at.desc())
    ).all()
    return [JobStatusOut.from_job(job) for job in jobs]
