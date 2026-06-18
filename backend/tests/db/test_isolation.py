"""Isolation tests: the suite migrates and targets the test DB, never the dev DB.

Covers the AC's second scenario — migrations are applied to the test database
automatically (the ``migrated_engine`` fixture does this at session start), and
no test reads or writes the development database.
"""

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pattern_mirror.core.config import get_settings

pytestmark = pytest.mark.db


def test_test_database_is_distinct_from_dev_database() -> None:
    settings = get_settings()
    if settings.test_database_url is None:
        pytest.skip("TEST_DATABASE_URL unset; CI runs against a disposable DATABASE_URL")

    assert settings.test_database_url != settings.database_url
    assert make_url(settings.test_database_url).database != make_url(settings.database_url).database


def test_db_session_is_bound_to_the_test_database(
    db_session: Session, test_database_url: str
) -> None:
    bound_database = db_session.connection().engine.url.database

    assert bound_database == make_url(test_database_url).database
