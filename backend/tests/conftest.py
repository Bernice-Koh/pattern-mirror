"""Shared fixtures for the backend test suite.

The database fixtures target the isolated ``pattern_mirror_test`` database
(``TEST_DATABASE_URL``), never the dev database, and apply the Alembic migrations
to it once per session. Each ``db_session`` runs inside a transaction that is
rolled back afterwards, so tests neither persist data nor see each other's writes.
When no Postgres is reachable, the database tests skip rather than fail, so the
non-database suite still runs offline.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import BlobNotFoundError
from pattern_mirror.main import create_app

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_MIGRATIONS_DIR = _BACKEND_DIR / "src" / "pattern_mirror" / "db" / "migrations"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """A TestClient over a freshly built app pinned to the test environment.

    The ``with`` block drives the app's lifespan (startup/shutdown), and the
    settings cache is reset so the app picks up the patched environment.
    """
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


class InMemoryBlobStore:
    """A ``BlobStore`` that keeps blobs in a dict, so tests never touch the filesystem."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def read(self, ref: str) -> bytes:
        try:
            return self._blobs[ref]
        except KeyError as exc:
            raise BlobNotFoundError(ref) from exc

    def write(self, ref: str, data: bytes) -> None:
        self._blobs[ref] = data


@pytest.fixture
def blob_store() -> InMemoryBlobStore:
    """A fresh in-memory blob store for a test."""
    return InMemoryBlobStore()


def _alembic_config(url: str) -> Config:
    """Build an Alembic config bound to ``url`` with absolute paths (cwd-independent)."""
    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """The URL of the database the suite runs against: the test DB, else the configured DB.

    ``TEST_DATABASE_URL`` is set locally so tests hit ``pattern_mirror_test``; it is
    unset in CI, where ``DATABASE_URL`` already points at a disposable container.
    """
    settings = get_settings()
    return settings.test_database_url or settings.database_url


@pytest.fixture(scope="session")
def migrated_engine(test_database_url: str) -> Iterator[Engine]:
    """A session-scoped engine on the test database, migrated to head once.

    Skips the whole database suite if Postgres is unreachable, so offline runs of
    the non-database tests still pass. Also refuses to run outside CI when the
    resolved test database is the dev database (``TEST_DATABASE_URL`` unset, empty,
    or pointed at ``DATABASE_URL``): rather than migrate or write the dev database,
    the suite skips. CI sets ``CI`` and uses a disposable ``DATABASE_URL``.
    """
    if test_database_url == get_settings().database_url and not os.environ.get("CI"):
        pytest.skip(
            "The resolved test database equals DATABASE_URL (the dev database) and CI "
            "is not set; set TEST_DATABASE_URL to an isolated database to run DB tests."
        )
    engine = create_engine(test_database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL not reachable for database tests: {exc}")

    command.upgrade(_alembic_config(test_database_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session wrapped in a transaction that is rolled back after the test.

    ``join_transaction_mode="create_savepoint"`` lets test code call ``commit()``
    without ending the outer transaction, so even committed writes are undone.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
