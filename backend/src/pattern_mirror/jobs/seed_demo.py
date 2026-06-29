"""Idempotent seeding of synthetic demo users (manager + HR) for local and demo environments.

Demo identities are sample data, not reference data, so they live in a seed script run on demand
(``python -m pattern_mirror.jobs.seed_demo``) rather than in a migration that would also populate
production. Each user is seeded with its role assignment so the mock login can land it on the
correct portal. Re-running only inserts what is missing, matched by ``external_user_id``.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User, UserRoleAssignment


@dataclass(frozen=True)
class UserSeed:
    """A synthetic demo user: identity and the single role they sign in as."""

    external_user_id: str
    legal_name: str
    email: str
    department: str
    role: UserRole


DEMO_MANAGER_EXTERNAL_ID = "demo-manager-1"
DEMO_HR_EXTERNAL_ID = "demo-hr-1"

_ROSTER: list[UserSeed] = [
    UserSeed(
        external_user_id=DEMO_MANAGER_EXTERNAL_ID,
        legal_name="Alex Tan",
        email="alex.tan@example.com",
        department="Markets",
        role=UserRole.manager,
    ),
    UserSeed(
        external_user_id=DEMO_HR_EXTERNAL_ID,
        legal_name="Jordan Lee",
        email="jordan.lee@example.com",
        department="Human Resources",
        role=UserRole.hr,
    ),
]


def seed_demo_users(session: Session) -> None:
    """Insert any roster user and role assignment not already present."""
    existing = {
        user.external_user_id: user
        for user in session.scalars(
            select(User).where(
                User.external_user_id.in_([seed.external_user_id for seed in _ROSTER])
            )
        ).all()
    }
    for seed in _ROSTER:
        user = existing.get(seed.external_user_id)
        if user is None:
            user = User(
                external_user_id=seed.external_user_id,
                legal_name=seed.legal_name,
                email=seed.email,
                department=seed.department,
            )
            session.add(user)
            session.flush()
        if session.get(UserRoleAssignment, {"user_id": user.id, "role": seed.role}) is None:
            session.add(UserRoleAssignment(user_id=user.id, role=seed.role))


def main() -> None:
    """Seed the demo roster against the configured database, committing once."""
    session = get_sessionmaker()()
    try:
        seed_demo_users(session)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":  # pragma: no cover
    main()
