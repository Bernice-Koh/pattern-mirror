"""Idempotent seeding of the synthetic demo data (users, subjects, documents) for local and demo.

Demo data is sample data, not reference data, so it lives in a seed script run on demand
(``python -m pattern_mirror.jobs.seed_demo``) rather than in a migration that would also populate
production. Users seed with their role assignment so the mock login lands on the correct portal;
the subjects and feedback documents (#23) give the Pattern Dashboard real content to mine.
Re-running only inserts what is missing — users by ``external_user_id``, subjects by
``external_ref``, documents by ``(owner_id, title)`` — so it is safe to run repeatedly.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.jobs.demo_dataset import DemoDataset, DocumentSeed, load_demo_dataset
from pattern_mirror.jobs.resume_fixtures import render_resume_pdf, resume_ref
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType, DocumentStatus, UserRole
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.services.blob_storage import BlobStore, get_blob_store


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


def _jd_id_by_role(session: Session, owner_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Map each role title to its JD document id, so feedback links to the JD for its role."""
    jds = session.scalars(
        select(Document).where(Document.owner_id == owner_id, Document.doc_type == DocType.jd)
    ).all()
    return {jd.role_title: jd.id for jd in jds if jd.role_title is not None}


def seed_demo_content(
    session: Session,
    dataset: DemoDataset | None = None,
    store: BlobStore | None = None,
) -> None:
    """Insert any demo subject and document not already present, owned by the demo manager.

    Subjects are matched by ``external_ref`` and documents by ``(owner_id, title)``, so a
    re-run is a no-op. Feedback documents are linked to their subject and seeded as submitted,
    representing the finished writing history the Pattern Dashboard mines. Each new subject also
    gets a synthetic resume written to the blob store, so the download link (#118) resolves.
    """
    dataset = dataset or load_demo_dataset()
    store = store or get_blob_store()
    manager = _demo_manager(session)

    refs = [subject.external_ref for subject in dataset.subjects]
    subjects_by_ref = {
        subject.external_ref: subject
        for subject in session.scalars(select(Subject).where(Subject.external_ref.in_(refs))).all()
    }
    for subject_seed in dataset.subjects:
        subject = subjects_by_ref.get(subject_seed.external_ref)
        if subject is None:
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
        # Backfill the resume for any subject missing one, not only ones created just now, so a
        # database seeded before resumes existed gets them on the next run (still idempotent once
        # the ref is set).
        if subject.resume_blob_ref is None:
            ref = resume_ref(subject.id)
            store.write(
                ref,
                render_resume_pdf(name=subject.legal_name, subject_type=subject.subject_type.value),
            )
            subject.resume_blob_ref = ref

    titles = [document.title for document in dataset.documents]
    existing_titles = set(
        session.scalars(
            select(Document.title).where(
                Document.owner_id == manager.id, Document.title.in_(titles)
            )
        ).all()
    )
    now = datetime.now(UTC)
    created: list[tuple[DocumentSeed, Document]] = []
    for document_seed in dataset.documents:
        if document_seed.title in existing_titles:
            continue
        subject_id = (
            subjects_by_ref[document_seed.subject_ref].id
            if document_seed.subject_ref is not None
            else None
        )
        is_submitted = document_seed.status is DocumentStatus.submitted
        document = Document(
            owner_id=manager.id,
            doc_type=document_seed.doc_type,
            title=document_seed.title,
            role_title=document_seed.role_title,
            subject_id=subject_id,
            content=document_seed.content,
            submitted_content=document_seed.content if is_submitted else None,
            submitted_at=now if is_submitted else None,
            status=document_seed.status,
        )
        session.add(document)
        created.append((document_seed, document))
    session.flush()

    # Link each new feedback note to the JD for its role and seed each new JD's criteria, so the
    # feedback drift check resolves a reference (#116). Only newly-created docs are touched, so a
    # re-run stays a no-op.
    jd_id_by_role = _jd_id_by_role(session, manager.id)
    for document_seed, document in created:
        if document.doc_type is DocType.feedback and document.role_title is not None:
            document.reference_jd_id = jd_id_by_role.get(document.role_title)
        for position, criterion in enumerate(document_seed.criteria):
            session.add(JdCriterion(jd_document_id=document.id, text=criterion, position=position))


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
