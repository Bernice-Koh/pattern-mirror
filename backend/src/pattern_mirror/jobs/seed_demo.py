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
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.jobs.demo_dataset import DemoDataset, DocumentSeed, load_demo_dataset
from pattern_mirror.jobs.resume_fixtures import render_resume_pdf, resume_ref
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType, DocumentStatus, UserRole
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.models.peer_corroboration import PeerCorroboration
from pattern_mirror.models.peer_feedback import PeerFeedback
from pattern_mirror.models.promotion_rubric import PromotionRubricCriterion
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

# The HR reviewer is fixed in code (they own no writeups, so they aren't part of the dataset's
# manager list); the managers who own documents come from the dataset, so the fixture can carry
# more than one without touching this file.
_HR_USER = UserSeed(
    external_user_id=DEMO_HR_EXTERNAL_ID,
    legal_name="Jordan Lee",
    email="jordan.lee@example.com",
    department="Human Resources",
    role=UserRole.hr,
)


def _roster(dataset: DemoDataset) -> list[UserSeed]:
    """The users to seed: the fixed HR reviewer plus every manager the dataset declares."""
    managers = [
        UserSeed(
            external_user_id=manager.external_user_id,
            legal_name=manager.legal_name,
            email=manager.email,
            department=manager.department,
            role=manager.role,
        )
        for manager in dataset.managers
    ]
    return [_HR_USER, *managers]


def seed_demo_users(session: Session, dataset: DemoDataset | None = None) -> None:
    """Insert any roster user and role assignment not already present.

    The roster is the HR reviewer plus the dataset's managers, so a fixture with more managers
    seeds more logins. Idempotent by ``external_user_id``.
    """
    dataset = dataset or load_demo_dataset()
    roster = _roster(dataset)
    existing = {
        user.external_user_id: user
        for user in session.scalars(
            select(User).where(
                User.external_user_id.in_([seed.external_user_id for seed in roster])
            )
        ).all()
    }
    for seed in roster:
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


def _managers_by_ref(session: Session, dataset: DemoDataset) -> dict[str, User]:
    """Resolve each dataset manager's ``external_user_id`` to its seeded ``User`` row.

    Every document names its owner by this ref, so the content seed can spread documents across
    managers. Seed the users first — a missing manager is a seeding-order bug, not a silent skip.
    """
    wanted = [manager.external_user_id for manager in dataset.managers]
    by_ref = {
        user.external_user_id: user
        for user in session.scalars(select(User).where(User.external_user_id.in_(wanted))).all()
    }
    missing = [ref for ref in wanted if ref not in by_ref]
    if missing:
        raise RuntimeError(
            f"demo manager is not seeded (owner {missing[0]}); run seed_demo_users first"
        )
    return by_ref


def _jd_id_by_owner_role(
    session: Session, owner_ids: list[uuid.UUID]
) -> dict[tuple[uuid.UUID, str], uuid.UUID]:
    """Map each (owner, role title) to its JD id, so feedback links to its own manager's JD.

    Keyed by owner as well as role so two managers can each run the same role without their
    feedback cross-linking to the other's JD (the dataset validator forbids one manager owning
    two JDs for one role, which would otherwise shadow).
    """
    jds = session.scalars(
        select(Document).where(Document.owner_id.in_(owner_ids), Document.doc_type == DocType.jd)
    ).all()
    return {(jd.owner_id, jd.role_title): jd.id for jd in jds if jd.role_title is not None}


def seed_demo_content(
    session: Session,
    dataset: DemoDataset | None = None,
    store: BlobStore | None = None,
) -> None:
    """Insert any demo subject and document not already present, owned by the manager it names.

    Each document names its owner (``owner_ref``); subjects match by ``external_ref`` and documents
    by ``(owner_id, title)``, so a re-run is a no-op. Feedback and promotion documents link to their
    subject; submitted ones are the finished writing history the Pattern Dashboard mines. Each new
    subject also gets a synthetic resume written to the blob store, so the download link (#118)
    resolves. Seed the users first (``seed_demo_users``) so every owner resolves.
    """
    dataset = dataset or load_demo_dataset()
    store = store or get_blob_store()
    managers_by_ref = _managers_by_ref(session, dataset)

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

    owner_ids = [manager.id for manager in managers_by_ref.values()]
    titles = [document.title for document in dataset.documents]
    # Documents dedup on (owner, title): two managers may legitimately share a title (e.g. a JD for
    # the same role), so scoping by owner keeps a re-run a no-op without collapsing them.
    existing_pairs = set(
        session.execute(
            select(Document.owner_id, Document.title).where(
                Document.owner_id.in_(owner_ids), Document.title.in_(titles)
            )
        ).all()
    )
    now = datetime.now(UTC)
    created: list[tuple[DocumentSeed, Document]] = []
    for document_seed in dataset.documents:
        owner = managers_by_ref[document_seed.owner_ref]
        if (owner.id, document_seed.title) in existing_pairs:
            continue
        subject_id = (
            subjects_by_ref[document_seed.subject_ref].id
            if document_seed.subject_ref is not None
            else None
        )
        is_submitted = document_seed.status is DocumentStatus.submitted
        # Back-date submitted history so the monthly trends span several months; a submitted doc
        # with no offset lands "now", a draft has no submission timestamp at all.
        submitted_at = (
            now - timedelta(days=document_seed.submitted_days_ago or 0) if is_submitted else None
        )
        document = Document(
            owner_id=owner.id,
            doc_type=document_seed.doc_type,
            title=document_seed.title,
            role_title=document_seed.role_title,
            subject_id=subject_id,
            content=document_seed.content,
            submitted_content=document_seed.content if is_submitted else None,
            submitted_at=submitted_at,
            status=document_seed.status,
        )
        session.add(document)
        created.append((document_seed, document))
    session.flush()

    # Link each new feedback note to its own manager's JD for that role and seed each new JD's
    # criteria, so the feedback drift check resolves a reference (#116). Only newly-created docs
    # are touched, so a re-run stays a no-op.
    jd_id_by_owner_role = _jd_id_by_owner_role(session, owner_ids)
    for document_seed, document in created:
        if document.doc_type is DocType.feedback and document.role_title is not None:
            document.reference_jd_id = jd_id_by_owner_role.get(
                (document.owner_id, document.role_title)
            )
        for position, criterion in enumerate(document_seed.criteria):
            session.add(JdCriterion(jd_document_id=document.id, text=criterion, position=position))

    _seed_peer_feedback(session, dataset, subjects_by_ref)
    _seed_promotion_rubrics(session, dataset)
    _seed_peer_corroboration(session, dataset, subjects_by_ref)


def _seed_promotion_rubrics(session: Session, dataset: DemoDataset) -> None:
    """Insert each target level's rubric criteria, the reference a promotion writeup drifts against.

    Keyed by ``level_label``; a level that already has any criteria is skipped whole, so a re-run is
    a no-op. Position follows dataset order.
    """
    already_seeded = set(
        session.scalars(select(PromotionRubricCriterion.level_label).distinct()).all()
    )
    for rubric in dataset.promotion_rubrics:
        if rubric.level_label in already_seeded:
            continue
        for position, criterion in enumerate(rubric.criteria):
            session.add(
                PromotionRubricCriterion(
                    level_label=rubric.level_label, text=criterion, position=position
                )
            )


def _seed_peer_corroboration(
    session: Session, dataset: DemoDataset, subjects_by_ref: dict[str | None, Subject]
) -> None:
    """Insert each employee's peer corroboration, the "what peers say" evidence against the rubric.

    Keyed by ``subject_id``; an employee that already has any corroboration is skipped whole, so a
    re-run is a no-op. Position follows dataset order.
    """
    already_seeded = set(session.scalars(select(PeerCorroboration.subject_id).distinct()).all())
    position_by_subject: dict[uuid.UUID, int] = {}
    for entry in dataset.peer_corroboration:
        subject = subjects_by_ref[entry.subject_ref]
        if subject.id in already_seeded:
            continue
        position = position_by_subject.get(subject.id, 0)
        position_by_subject[subject.id] = position + 1
        session.add(
            PeerCorroboration(
                subject_id=subject.id,
                criterion=entry.criterion,
                corroborated=entry.corroborated,
                evidence=entry.evidence,
                position=position,
            )
        )


def _seed_peer_feedback(
    session: Session, dataset: DemoDataset, subjects_by_ref: dict[str | None, Subject]
) -> None:
    """Insert each employee's peer feedback, the reference a promotion writeup drifts against.

    Peer feedback rows carry no natural key, so a subject that already has any is skipped whole
    rather than deduplicated row by row — keeping a re-run a no-op. Position follows dataset order.
    """
    already_seeded = set(session.scalars(select(PeerFeedback.subject_id).distinct()).all())
    position_by_subject: dict[uuid.UUID, int] = {}
    for peer_seed in dataset.peer_feedback:
        subject = subjects_by_ref[peer_seed.subject_ref]
        if subject.id in already_seeded:
            continue
        position = position_by_subject.get(subject.id, 0)
        position_by_subject[subject.id] = position + 1
        session.add(
            PeerFeedback(
                subject_id=subject.id,
                author_label=peer_seed.author_label,
                strengths=peer_seed.strengths,
                development=peer_seed.development,
                overall=peer_seed.overall,
                position=position,
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
