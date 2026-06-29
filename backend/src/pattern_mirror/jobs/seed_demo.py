"""Idempotent seeding of the synthetic demo data (users, subjects, documents) for local and demo.

Demo data is sample data, not reference data, so it lives in a seed script run on demand
(``python -m pattern_mirror.jobs.seed_demo``) rather than in a migration that would also populate
production. Users seed with their role assignment so the mock login lands on the correct portal;
the subjects and feedback documents (#23) give the Pattern Dashboard real content to mine.
Re-running only inserts what is missing — users by ``external_user_id``, subjects by
``external_ref``, documents by ``(owner_id, title)`` — so it is safe to run repeatedly.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.jobs.demo_dataset import DemoDataset, load_demo_dataset
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocumentStatus, UserRole
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment


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


def _demo_manager(session: Session) -> User:
    """The demo manager who owns the seeded documents; seed the users first."""
    manager = session.scalar(select(User).where(User.external_user_id == DEMO_MANAGER_EXTERNAL_ID))
    if manager is None:
        raise RuntimeError("demo manager is not seeded; run seed_demo_users first")
    return manager


def seed_demo_content(session: Session, dataset: DemoDataset | None = None) -> None:
    """Insert any demo subject and document not already present, owned by the demo manager.

    Subjects are matched by ``external_ref`` and documents by ``(owner_id, title)``, so a
    re-run is a no-op. Feedback documents are linked to their subject and seeded as submitted,
    representing the finished writing history the Pattern Dashboard mines.
    """
    dataset = dataset or load_demo_dataset()
    manager = _demo_manager(session)

    refs = [subject.external_ref for subject in dataset.subjects]
    subjects_by_ref = {
        subject.external_ref: subject
        for subject in session.scalars(select(Subject).where(Subject.external_ref.in_(refs))).all()
    }
    for subject_seed in dataset.subjects:
        if subject_seed.external_ref not in subjects_by_ref:
            subject = Subject(
                subject_type=subject_seed.subject_type,
                legal_name=subject_seed.legal_name,
                external_ref=subject_seed.external_ref,
                gender=subject_seed.gender,
                age_band=subject_seed.age_band,
            )
            session.add(subject)
            session.flush()
            subjects_by_ref[subject_seed.external_ref] = subject

    titles = [document.title for document in dataset.documents]
    existing_titles = set(
        session.scalars(
            select(Document.title).where(
                Document.owner_id == manager.id, Document.title.in_(titles)
            )
        ).all()
    )
    now = datetime.now(UTC)
    for document_seed in dataset.documents:
        if document_seed.title in existing_titles:
            continue
        subject_id = (
            subjects_by_ref[document_seed.subject_ref].id
            if document_seed.subject_ref is not None
            else None
        )
        session.add(
            Document(
                owner_id=manager.id,
                doc_type=document_seed.doc_type,
                title=document_seed.title,
                role_title=document_seed.role_title,
                subject_id=subject_id,
                content=document_seed.content,
                submitted_content=document_seed.content,
                submitted_at=now,
                status=DocumentStatus.submitted,
            )
        )


def main() -> None:
    """Seed the demo users and content against the configured database, committing once."""
    session = get_sessionmaker()()
    try:
        seed_demo_users(session)
        seed_demo_content(session)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":  # pragma: no cover
    main()
