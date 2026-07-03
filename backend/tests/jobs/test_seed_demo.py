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
from pattern_mirror.models.enums import DocType, DocumentStatus, UserRole
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.jd_criteria import JdCriterion


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
