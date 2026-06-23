"""seed_demo_users inserts the demo roster, and re-running it is idempotent."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.jobs.seed_demo import DEMO_MANAGER_EXTERNAL_ID, seed_demo_users
from pattern_mirror.models.identity import User

pytestmark = pytest.mark.db


def test_seeds_the_demo_manager(db_session: Session) -> None:
    seed_demo_users(db_session)
    db_session.flush()

    user = db_session.scalar(select(User).where(User.external_user_id == DEMO_MANAGER_EXTERNAL_ID))
    assert user is not None
    assert user.email


def test_is_idempotent(db_session: Session) -> None:
    seed_demo_users(db_session)
    db_session.flush()
    seed_demo_users(db_session)
    db_session.flush()

    count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.external_user_id == DEMO_MANAGER_EXTERNAL_ID)
    )
    assert count == 1
