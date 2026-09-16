"""Feedback endpoints (spec PR-12).

POST /api/v1/feedback -> 201, one row per submission (not one row per user —
a history, not a single mutable rating).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession, rate_limit_feedback
from app.api.schemas import FeedbackCreate, FeedbackOut
from app.db.models import Feedback

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=FeedbackOut,
    dependencies=[Depends(rate_limit_feedback)],
)
def submit_feedback(body: FeedbackCreate, db: DbSession, user: CurrentUser) -> Feedback:
    feedback = Feedback(user_id=user.id, rating=body.rating, comment=body.comment)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
