"""Admin endpoints (specs AD-01 user management, AD-02 feedback inbox).

Every route here is gated by ``require_admin`` — a role check on top of the
same JWT auth everyone else uses, not a separate auth system (decision D1).
Nothing in this app can self-promote a user to admin; that's a manual DB
update or ``scripts/promote_admin.py``, deliberately outside the UI.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentAdmin, DbSession
from app.api.schemas import AdminFeedbackOut, AdminUserOut
from app.api.search import escape_like
from app.db.models import Feedback, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _owned_target(db: DbSession, user_id: uuid.UUID, admin: User) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if target.id == admin.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot suspend your own account")
    if target.is_admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "cannot suspend another admin")
    return target


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: DbSession,
    _admin: CurrentAdmin,
    q: Annotated[str | None, Query(max_length=200)] = None,
    include_suspended: bool = True,
) -> list[User]:
    stmt = select(User)
    if not include_suspended:
        stmt = stmt.where(User.suspended_at.is_(None))
    if q and q.strip():
        term = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            (User.email.ilike(term, escape="\\")) | (User.username.ilike(term, escape="\\"))
        )
    return list(db.scalars(stmt.order_by(User.created_at.desc())).all())


@router.post("/users/{user_id}/suspend", response_model=AdminUserOut)
def suspend_user(user_id: uuid.UUID, db: DbSession, admin: CurrentAdmin) -> User:
    target = _owned_target(db, user_id, admin)
    if target.suspended_at is None:  # idempotent
        target.suspended_at = datetime.now(UTC)
        db.commit()
        db.refresh(target)
    return target


@router.post("/users/{user_id}/unsuspend", response_model=AdminUserOut)
def unsuspend_user(user_id: uuid.UUID, db: DbSession, admin: CurrentAdmin) -> User:
    target = _owned_target(db, user_id, admin)
    if target.suspended_at is not None:
        target.suspended_at = None
        db.commit()
        db.refresh(target)
    return target


@router.get("/feedback", response_model=list[AdminFeedbackOut])
def list_feedback(db: DbSession, _admin: CurrentAdmin) -> list[AdminFeedbackOut]:
    rows = db.scalars(select(Feedback).order_by(Feedback.created_at.desc())).all()
    return [
        AdminFeedbackOut(
            id=row.id,
            rating=row.rating,
            comment=row.comment,
            created_at=row.created_at,
            user_email=row.user.email,
            username=row.user.username,
        )
        for row in rows
    ]
