"""Idempotent seeding of synthetic demo managers for local and demo environments.

Demo identities are sample data, not reference data, so they live in a seed script run
on demand (``python -m pattern_mirror.jobs.seed_demo``) rather than in a migration that
would also populate production. ``api.deps.get_current_user`` resolves the manager the
analyze endpoint attributes documents to until real auth exists. The roster is a list so
adding the other demo personas later is an append, not a rewrite.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.models.identity import User


@dataclass(frozen=True)
class ManagerSeed:
    """A synthetic demo manager: identity only, no demographics or bias signal."""

    external_user_id: str
    legal_name: str
    email: str
    department: str


DEMO_MANAGER_EXTERNAL_ID = "demo-manager-1"

_ROSTER: list[ManagerSeed] = [
    ManagerSeed(
        external_user_id=DEMO_MANAGER_EXTERNAL_ID,
        legal_name="Alex Tan",
        email="alex.tan@example.com",
        department="Markets",
    ),
]


def seed_demo_users(session: Session) -> None:
    """Insert any roster manager not already present, matched by ``external_user_id``."""
    present = set(
        session.scalars(
            select(User.external_user_id).where(
                User.external_user_id.in_([manager.external_user_id for manager in _ROSTER])
            )
        ).all()
    )
    session.add_all(
        User(
            external_user_id=manager.external_user_id,
            legal_name=manager.legal_name,
            email=manager.email,
            department=manager.department,
        )
        for manager in _ROSTER
        if manager.external_user_id not in present
    )


def main() -> None:
    """Seed the demo roster against the configured database, committing once."""
    session = get_sessionmaker()()
    try:
        seed_demo_users(session)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
