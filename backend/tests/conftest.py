from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session whose writes are rolled back at the end of the test.

    Requires a reachable database (mark such tests ``integration``). The outer
    transaction is never committed; ``session.commit()`` inside a test creates a
    savepoint instead.
    """
    from app.db.session import engine

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
