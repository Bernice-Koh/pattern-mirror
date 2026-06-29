"""The document lifecycle service: create a draft, autosave it, submit it, owner-scoped."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.models.documents import AnalysisRun
from pattern_mirror.models.enums import DocType, DocumentStatus
from pattern_mirror.models.identity import User
from pattern_mirror.services.documents import (
    create_draft,
    get_draft,
    submit_document,
    update_draft,
)

pytestmark = pytest.mark.db


def _manager(db_session: Session, external_id: str = "docs-manager") -> User:
    user = User(
        external_user_id=external_id,
        legal_name="Docs Manager",
        email=f"{external_id}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_create_draft_starts_empty_and_owned(db_session: Session) -> None:
    owner = _manager(db_session)

    document = create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd)

    assert document.owner_id == owner.id
    assert document.status is DocumentStatus.draft
    assert document.content == ""
    assert document.submitted_content is None


def test_update_draft_round_trips_title_and_content(db_session: Session) -> None:
    owner = _manager(db_session)
    document = create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd)

    update_draft(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        title="Senior Engineer",
        content="We want a digital native.",
    )

    restored = get_draft(db_session, document_id=document.id, owner_id=owner.id)
    assert restored.title == "Senior Engineer"
    assert restored.content == "We want a digital native."
    assert restored.status is DocumentStatus.draft


def test_update_draft_runs_no_analysis(db_session: Session) -> None:
    owner = _manager(db_session)
    document = create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd)

    update_draft(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        title=None,
        content="We want a digital native.",
    )

    runs = db_session.scalar(
        select(func.count()).select_from(AnalysisRun).where(AnalysisRun.document_id == document.id)
    )
    assert runs == 0


def test_submit_captures_final_text_and_transitions(db_session: Session) -> None:
    owner = _manager(db_session)
    document = create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd)
    update_draft(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        title="Role",
        content="draft text",
    )

    submitted = submit_document(
        db_session, document_id=document.id, owner_id=owner.id, content="final text"
    )

    assert submitted.status is DocumentStatus.submitted
    assert submitted.content == "final text"
    assert submitted.submitted_content == "final text"
    assert submitted.submitted_at is not None


@pytest.mark.parametrize("action", ["get", "update", "submit"])
def test_a_foreign_document_is_not_found(db_session: Session, action: str) -> None:
    owner = _manager(db_session, "docs-owner")
    other = _manager(db_session, "docs-other")
    document = create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd)

    with pytest.raises(DocumentNotFoundError):
        if action == "get":
            get_draft(db_session, document_id=document.id, owner_id=other.id)
        elif action == "update":
            update_draft(
                db_session, document_id=document.id, owner_id=other.id, title=None, content="x"
            )
        else:
            submit_document(db_session, document_id=document.id, owner_id=other.id, content="x")


def test_an_absent_document_is_not_found(db_session: Session) -> None:
    owner = _manager(db_session)

    with pytest.raises(DocumentNotFoundError):
        get_draft(db_session, document_id=uuid.uuid4(), owner_id=owner.id)
