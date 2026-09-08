"""Project endpoints.

M2 needs only "create" so analyses have somewhere to live. Full CRUD (rename,
archive, search) is spec PR-07 (M3).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.schemas import ProjectCreate, ProjectOut
from app.db.models import Project

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
def create_project(body: ProjectCreate, db: DbSession, user: CurrentUser) -> Project:
    project = Project(name=body.name, user_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: DbSession, user: CurrentUser) -> list[Project]:
    return list(
        db.scalars(
            select(Project)
            .where(Project.user_id == user.id, Project.archived_at.is_(None))
            .order_by(Project.created_at.desc())
        ).all()
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "project not found or not yours")
    return project
