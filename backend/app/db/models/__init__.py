"""ORM model registry.

Import every model module here so that ``Base.metadata`` is fully populated
before Alembic autogenerate or ``create_all`` runs.

M2 (ADR-0002) adds the job state machine and analysis output tables. Auth
columns on ``users`` come in M3 (spec GU-01).
"""

from app.db.base import Base
from app.db.models.analysis import Analysis, Comment, Community, Node, RawComment
from app.db.models.auth_token import AuthToken, TokenPurpose
from app.db.models.job import AnalysisJob
from app.db.models.project import Project
from app.db.models.user import User

__all__ = [
    "Analysis",
    "AnalysisJob",
    "AuthToken",
    "Base",
    "Comment",
    "Community",
    "Node",
    "Project",
    "RawComment",
    "TokenPurpose",
    "User",
]
