"""seed_demo_users inserts the manager and HR roster with roles, and re-running is idempotent."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.jobs import seed_demo
from pattern_mirror.jobs.seed_demo import (
    DEMO_HR_EXTERNAL_ID,
    DEMO_MANAGER_EXTERNAL_ID,
    seed_demo_users,
)
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User, UserRoleAssignment


def _user(db_session: Session, external_user_id: str) -> User:
    user = db_session.scalar(select(User).where(User.external_user_id == external_user_id))
    assert user is not None
    return user


@pytest.mark.db
def test_seeds_the_manager_with_the_manager_role(db_session: Session) -> None:
    seed_demo_users(db_session)
    db_session.flush()

    user = _user(db_session, DEMO_MANAGER_EXTERNAL_ID)
    assert user.email
    assert {assignment.role for assignment in user.roles} == {UserRole.manager}


@pytest.mark.db
def test_seeds_the_hr_user_with_the_hr_role(db_session: Session) -> None:
    seed_demo_users(db_session)
    db_session.flush()

    user = _user(db_session, DEMO_HR_EXTERNAL_ID)
    assert {assignment.role for assignment in user.roles} == {UserRole.hr}


@pytest.mark.db
def test_is_idempotent(db_session: Session) -> None:
    seed_demo_users(db_session)
    db_session.flush()
    seed_demo_users(db_session)
    db_session.flush()

    users = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.external_user_id.in_([DEMO_MANAGER_EXTERNAL_ID, DEMO_HR_EXTERNAL_ID]))
    )
    roles = db_session.scalar(select(func.count()).select_from(UserRoleAssignment))
    assert users == 2
    assert roles == 2


def test_main_seeds_then_commits_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            events.append("commit")

        def close(self) -> None:
            events.append("close")

    fake = FakeSession()
    monkeypatch.setattr(seed_demo, "get_sessionmaker", lambda: lambda: fake)
    monkeypatch.setattr(seed_demo, "seed_demo_users", lambda session: events.append("seed"))

    seed_demo.main()

    assert events == ["seed", "commit", "close"]
