"""Promote an existing account to admin (spec AD-01).

Deliberately not an API endpoint or a UI button — nothing in the app can grant
itself admin access. This is the one door in, meant to be run by whoever holds
the database credentials.

Run:  ``uv run python scripts/promote_admin.py someone@example.com``
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.models.user import ADMIN_ROLE, User
from app.db.session import SessionLocal


def promote(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"no account with email {email!r}")
            raise SystemExit(1)
        if user.role == ADMIN_ROLE:
            print(f"{user.username} <{user.email}> is already an admin")
            return
        user.role = ADMIN_ROLE
        db.commit()
        print(f"{user.username} <{user.email}> is now an admin")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: uv run python scripts/promote_admin.py <email>")
        raise SystemExit(1)
    promote(sys.argv[1])
