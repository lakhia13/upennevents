"""Repository tests need a real Postgres (ARRAY, JSONB, ON CONFLICT, generated
columns aren't meaningfully fakeable with SQLite). They're skipped unless
TEST_DATABASE_URL points at a throwaway instance, e.g.:

    docker run -d --rm -p 55432:5432 -e POSTGRES_PASSWORD=test postgres:16
    TEST_DATABASE_URL=postgresql+psycopg://postgres:test@localhost:55432/postgres \
        pytest tests/test_repositories

Every test runs inside a transaction that is rolled back afterwards, so the
schema is created once per session and tests never see each other's data.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from penn_events.db.models import Base

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("set TEST_DATABASE_URL to run repository tests against real Postgres")
    engine = create_engine(TEST_DATABASE_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
