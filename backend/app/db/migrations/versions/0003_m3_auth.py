"""m3 auth: real accounts on users, plus the auth_tokens table

Drops the M2 dev-placeholder account first: the new ``users`` columns are NOT
NULL and that row has no password. Anything the dev user owned goes with it
(``projects.user_id`` cascades), which is intended — it was seed data, and M2
never had real accounts to preserve.

Revision ID: 0003_m3_auth
Revises: 0002_m2_schema
Create Date: 2026-09-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_m3_auth"
down_revision: str | None = "0002_m2_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
_DEV_PROJECT_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    # Must come before the NOT NULL columns below — see the module docstring.
    op.execute(sa.text(f"DELETE FROM users WHERE id = '{_DEV_USER_ID}'"))

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_tokens")),
    )
    op.create_index(op.f("ix_auth_tokens_expires_at"), "auth_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_auth_tokens_purpose"), "auth_tokens", ["purpose"], unique=False)
    op.create_index(op.f("ix_auth_tokens_token_hash"), "auth_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)

    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=False))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=False))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False))
    op.add_column("users", sa.Column("subscription_plan", sa.String(length=20), nullable=False))
    op.add_column("users", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_column("users", "trial_ends_at")
    op.drop_column("users", "subscription_plan")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "username")
    op.drop_index(op.f("ix_auth_tokens_user_id"), table_name="auth_tokens")
    op.drop_index(op.f("ix_auth_tokens_token_hash"), table_name="auth_tokens")
    op.drop_index(op.f("ix_auth_tokens_purpose"), table_name="auth_tokens")
    op.drop_index(op.f("ix_auth_tokens_expires_at"), table_name="auth_tokens")
    op.drop_table("auth_tokens")

    # Put 0002's dev placeholder back so downgrading lands in the world M2 expects.
    op.bulk_insert(
        sa.table("users", sa.column("id", sa.Uuid), sa.column("email", sa.String)),
        [{"id": _DEV_USER_ID, "email": "dev@orbitlink.local"}],
    )
    op.bulk_insert(
        sa.table(
            "projects",
            sa.column("id", sa.Uuid),
            sa.column("user_id", sa.Uuid),
            sa.column("name", sa.String),
        ),
        [{"id": _DEV_PROJECT_ID, "user_id": _DEV_USER_ID, "name": "Dev project"}],
    )
