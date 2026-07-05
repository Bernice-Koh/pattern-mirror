"""The seed job inserts the user roster and the demo content, and re-running is idempotent."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.conftest import InMemoryBlobStore

from pattern_mirror.jobs import seed_demo
from pattern_mirror.jobs.demo_dataset import load_demo_dataset
from pattern_mirror.jobs.resume_fixtures import resume_ref
from pattern_mirror.jobs.seed_demo import (
    DEMO_HR_EXTERNAL_ID,
    DEMO_MANAGER_EXTERNAL_ID,
    seed_demo_content,
    seed_demo_users,
)
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType, DocumentStatus, SubjectType, UserRole
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.models.peer_corroboration import PeerCorroboration
from pattern_mirror.models.peer_feedback import PeerFeedback
from pattern_mirror.models.promotion_rubric import PromotionRubricCriterion


def _user(db_session: Session, external_user_id: str) -> User:
    user = db_session.scalar(select(User).where(User.external_user_id == external_user_id))
    assert user is not None
    return user


def _seed(db_session: Session, store: InMemoryBlobStore) -> None:
    """Seed users then content against the given blob store, flushing so queries see the writes."""
    seed_demo_users(db_session)
    db_session.flush()
    seed_demo_content(db_session, store=store)
    db_session.flush()


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


@pytest.mark.db
def test_seeds_subjects_and_feedback_owned_by_the_manager(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    dataset = load_demo_dataset()
    manager = _user(db_session, DEMO_MANAGER_EXTERNAL_ID)
    subjects = db_session.scalar(select(func.count()).select_from(Subject))
    documents = db_session.scalar(
        select(func.count()).select_from(Document).where(Document.owner_id == manager.id)
    )
    assert subjects == len(dataset.subjects)
    assert documents == len(dataset.documents)


@pytest.mark.db
def test_feedback_document_carries_its_subject_link(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    feedback = db_session.scalar(
        select(Document).where(Document.doc_type == DocType.feedback).limit(1)
    )
    assert feedback is not None
    assert feedback.subject_id is not None


@pytest.mark.db
def test_seeds_a_resume_blob_for_each_subject(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    subjects = db_session.scalars(select(Subject)).all()
    assert subjects
    for subject in subjects:
        assert subject.resume_blob_ref == resume_ref(subject.id)
        assert blob_store.read(subject.resume_blob_ref).startswith(b"%PDF-")


@pytest.mark.db
def test_backfills_a_resume_for_a_subject_that_predates_resumes(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    seed_demo_users(db_session)
    db_session.flush()
    existing = load_demo_dataset().subjects[0]
    subject = Subject(
        subject_type=existing.subject_type,
        legal_name=existing.legal_name,
        external_ref=existing.external_ref,
        resume_blob_ref=None,
    )
    db_session.add(subject)
    db_session.flush()

    seed_demo_content(db_session, store=blob_store)
    db_session.flush()

    db_session.refresh(subject)
    assert subject.resume_blob_ref == resume_ref(subject.id)
    assert blob_store.read(subject.resume_blob_ref).startswith(b"%PDF-")


@pytest.mark.db
def test_seed_content_is_idempotent(db_session: Session, blob_store: InMemoryBlobStore) -> None:
    _seed(db_session, blob_store)
    seed_demo_content(db_session, store=blob_store)
    db_session.flush()

    dataset = load_demo_dataset()
    subjects = db_session.scalar(select(func.count()).select_from(Subject))
    documents = db_session.scalar(select(func.count()).select_from(Document))
    assert subjects == len(dataset.subjects)
    assert documents == len(dataset.documents)


@pytest.mark.db
def test_seeds_jd_criteria_for_the_jds(db_session: Session, blob_store: InMemoryBlobStore) -> None:
    _seed(db_session, blob_store)

    dataset = load_demo_dataset()
    expected = sum(len(document.criteria) for document in dataset.documents)
    seeded = db_session.scalar(select(func.count()).select_from(JdCriterion))
    assert expected > 0
    assert seeded == expected


@pytest.mark.db
def test_feedback_links_to_the_jd_for_its_role(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    jd = db_session.scalar(
        select(Document).where(
            Document.doc_type == DocType.jd, Document.role_title == "Markets Analyst"
        )
    )
    feedback = db_session.scalar(
        select(Document)
        .where(Document.doc_type == DocType.feedback, Document.role_title == "Markets Analyst")
        .limit(1)
    )
    assert jd is not None
    assert feedback is not None
    assert feedback.reference_jd_id == jd.id


@pytest.mark.db
def test_seeds_a_draft_feedback_linked_to_its_jd(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    draft = db_session.scalar(
        select(Document).where(
            Document.doc_type == DocType.feedback, Document.status == DocumentStatus.draft
        )
    )
    assert draft is not None
    assert draft.submitted_at is None
    assert draft.submitted_content is None
    assert draft.reference_jd_id is not None
    assert draft.subject_id is not None


@pytest.mark.db
def test_seeds_peer_feedback_for_employees(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    dataset = load_demo_dataset()
    seeded = db_session.scalar(select(func.count()).select_from(PeerFeedback))
    assert len(dataset.peer_feedback) > 0
    assert seeded == len(dataset.peer_feedback)


@pytest.mark.db
def test_peer_feedback_hangs_off_an_employee_subject(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    row = db_session.scalar(select(PeerFeedback).limit(1))
    assert row is not None
    subject = db_session.get(Subject, row.subject_id)
    assert subject is not None
    assert subject.subject_type is SubjectType.employee


@pytest.mark.db
def test_promotion_draft_carries_its_employee_subject(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    promotion = db_session.scalar(
        select(Document).where(Document.doc_type == DocType.promotion).limit(1)
    )
    assert promotion is not None
    assert promotion.status is DocumentStatus.draft
    assert promotion.subject_id is not None
    subject = db_session.get(Subject, promotion.subject_id)
    assert subject is not None
    assert subject.subject_type is SubjectType.employee


@pytest.mark.db
def test_seeds_promotion_rubric_criteria(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    dataset = load_demo_dataset()
    expected = sum(len(rubric.criteria) for rubric in dataset.promotion_rubrics)
    seeded = db_session.scalar(select(func.count()).select_from(PromotionRubricCriterion))
    assert expected > 0
    assert seeded == expected


@pytest.mark.db
def test_seeds_peer_corroboration_for_employees(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    dataset = load_demo_dataset()
    seeded = db_session.scalar(select(func.count()).select_from(PeerCorroboration))
    assert len(dataset.peer_corroboration) > 0
    assert seeded == len(dataset.peer_corroboration)


@pytest.mark.db
def test_peer_corroboration_hangs_off_an_employee_subject(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)

    row = db_session.scalar(select(PeerCorroboration).limit(1))
    assert row is not None
    subject = db_session.get(Subject, row.subject_id)
    assert subject is not None
    assert subject.subject_type is SubjectType.employee


@pytest.mark.db
def test_reseeding_does_not_duplicate_promotion_rubric(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)
    first = db_session.scalar(select(func.count()).select_from(PromotionRubricCriterion))
    seed_demo_content(db_session, store=blob_store)
    db_session.flush()
    second = db_session.scalar(select(func.count()).select_from(PromotionRubricCriterion))

    assert second == first


@pytest.mark.db
def test_reseeding_does_not_duplicate_peer_corroboration(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)
    first = db_session.scalar(select(func.count()).select_from(PeerCorroboration))
    seed_demo_content(db_session, store=blob_store)
    db_session.flush()
    second = db_session.scalar(select(func.count()).select_from(PeerCorroboration))

    assert second == first


@pytest.mark.db
def test_reseeding_does_not_duplicate_peer_feedback(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)
    first = db_session.scalar(select(func.count()).select_from(PeerFeedback))
    seed_demo_content(db_session, store=blob_store)
    db_session.flush()
    second = db_session.scalar(select(func.count()).select_from(PeerFeedback))

    assert second == first


@pytest.mark.db
def test_reseeding_does_not_duplicate_jd_criteria(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    _seed(db_session, blob_store)
    first = db_session.scalar(select(func.count()).select_from(JdCriterion))
    seed_demo_content(db_session, store=blob_store)
    db_session.flush()
    second = db_session.scalar(select(func.count()).select_from(JdCriterion))

    assert second == first


@pytest.mark.db
def test_seed_content_requires_the_manager(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    with pytest.raises(RuntimeError, match="demo manager is not seeded"):
        seed_demo_content(db_session, store=blob_store)


def test_main_seeds_then_commits_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class FakeSession:
        def commit(self) -> None:
            events.append("commit")

        def close(self) -> None:
            events.append("close")

    fake = FakeSession()
    monkeypatch.setattr(seed_demo, "get_sessionmaker", lambda: lambda: fake)
    monkeypatch.setattr(seed_demo, "seed_demo_users", lambda session: events.append("seed-users"))
    monkeypatch.setattr(
        seed_demo, "seed_demo_content", lambda session: events.append("seed-content")
    )

    seed_demo.main()

    assert events == ["seed-users", "seed-content", "commit", "close"]
