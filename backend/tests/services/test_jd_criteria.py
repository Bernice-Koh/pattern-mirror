"""JD-criteria authoring: draft logs a run without persisting, confirm is an idempotent replace."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import (
    DocumentNotFoundError,
    DocumentTypeMismatchError,
    LlmClientUnavailableError,
)
from pattern_mirror.engine.jd_criteria_extraction import (
    JdCriteriaDraftResult,
    JdCriterionDraft,
)
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import AgentName, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.services.documents import create_draft
from pattern_mirror.services.jd_criteria import (
    draft_jd_criteria,
    list_jd_criteria,
    replace_jd_criteria,
)

pytestmark = pytest.mark.db


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeExtractionClient:
    def __init__(self, *texts: str) -> None:
        self._result = JdCriteriaDraftResult(
            criteria=[JdCriterionDraft(text=text) for text in texts]
        )
        self._completion = _FakeCompletion(_FakeUsage(400, 80))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._result, self._completion


def _manager(db_session: Session, external_id: str = "jd-criteria-manager") -> User:
    user = User(
        external_user_id=external_id,
        legal_name="Criteria Manager",
        email=f"{external_id}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _jd(db_session: Session, owner: User) -> uuid.UUID:
    return create_draft(db_session, owner_id=owner.id, doc_type=DocType.jd).id


def test_draft_returns_criteria_and_logs_a_run_without_persisting(db_session: Session) -> None:
    owner = _manager(db_session)
    jd_id = _jd(db_session, owner)
    client = _FakeExtractionClient("Python proficiency", "Stakeholder management")

    drafts = draft_jd_criteria(
        db_session,
        document_id=jd_id,
        owner_id=owner.id,
        jd_text="Senior engineer role.",
        client=client,
        model="m",
    )

    assert drafts == ["Python proficiency", "Stakeholder management"]
    # The draft is unconfirmed: it logs an audit row but writes no jd_criteria.
    run = db_session.scalars(select(AgentRun).where(AgentRun.document_id == jd_id)).one()
    assert run.agent_name is AgentName.jd_criteria_drafter
    assert db_session.scalars(select(JdCriterion)).all() == []


def test_draft_without_a_client_raises(db_session: Session) -> None:
    owner = _manager(db_session)
    jd_id = _jd(db_session, owner)

    with pytest.raises(LlmClientUnavailableError):
        draft_jd_criteria(
            db_session,
            document_id=jd_id,
            owner_id=owner.id,
            jd_text="x",
            client=None,
            model="m",
        )


def test_draft_on_a_non_jd_raises(db_session: Session) -> None:
    owner = _manager(db_session)
    feedback = create_draft(db_session, owner_id=owner.id, doc_type=DocType.feedback)

    with pytest.raises(DocumentTypeMismatchError):
        draft_jd_criteria(
            db_session,
            document_id=feedback.id,
            owner_id=owner.id,
            jd_text="x",
            client=_FakeExtractionClient("a"),
            model="m",
        )


def test_draft_on_a_foreign_document_raises(db_session: Session) -> None:
    owner = _manager(db_session)
    other = _manager(db_session, external_id="jd-criteria-other")
    jd_id = _jd(db_session, owner)

    with pytest.raises(DocumentNotFoundError):
        draft_jd_criteria(
            db_session,
            document_id=jd_id,
            owner_id=other.id,
            jd_text="x",
            client=_FakeExtractionClient("a"),
            model="m",
        )


def test_replace_writes_the_confirmed_set_in_order(db_session: Session) -> None:
    owner = _manager(db_session)
    jd_id = _jd(db_session, owner)

    confirmed = replace_jd_criteria(
        db_session,
        document_id=jd_id,
        owner_id=owner.id,
        texts=["First criterion", "Second criterion"],
    )

    assert confirmed == ["First criterion", "Second criterion"]
    rows = db_session.scalars(
        select(JdCriterion)
        .where(JdCriterion.jd_document_id == jd_id)
        .order_by(JdCriterion.position)
    ).all()
    assert [(row.position, row.text) for row in rows] == [
        (0, "First criterion"),
        (1, "Second criterion"),
    ]


def test_replace_is_idempotent_and_does_not_accumulate(db_session: Session) -> None:
    owner = _manager(db_session)
    jd_id = _jd(db_session, owner)

    replace_jd_criteria(
        db_session, document_id=jd_id, owner_id=owner.id, texts=["Old one", "Old two"]
    )
    replace_jd_criteria(db_session, document_id=jd_id, owner_id=owner.id, texts=["New only"])

    assert list_jd_criteria(db_session, document_id=jd_id, owner_id=owner.id) == ["New only"]


def test_replace_strips_blanks_and_deduplicates(db_session: Session) -> None:
    owner = _manager(db_session)
    jd_id = _jd(db_session, owner)

    confirmed = replace_jd_criteria(
        db_session,
        document_id=jd_id,
        owner_id=owner.id,
        texts=["  Leadership  ", "", "leadership", "Mentoring"],
    )

    assert confirmed == ["Leadership", "Mentoring"]


def test_list_is_owner_scoped(db_session: Session) -> None:
    owner = _manager(db_session)
    other = _manager(db_session, external_id="jd-criteria-list-other")
    jd_id = _jd(db_session, owner)
    replace_jd_criteria(db_session, document_id=jd_id, owner_id=owner.id, texts=["A"])

    with pytest.raises(DocumentNotFoundError):
        list_jd_criteria(db_session, document_id=jd_id, owner_id=other.id)
