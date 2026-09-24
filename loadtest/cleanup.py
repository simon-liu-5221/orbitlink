"""Deletes every user this loadtest suite has ever created (email prefix
``loadtest-``), along with their projects/jobs/analyses via cascade.

    cd backend
    uv run python ../loadtest/cleanup.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import delete

from app.db.models import User
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        result = db.execute(delete(User).where(User.email.like("loadtest-%")))
        db.commit()
        print(f"deleted {result.rowcount} loadtest user(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
