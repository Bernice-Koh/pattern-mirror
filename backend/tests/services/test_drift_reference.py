"""Resolving a document's drift reference from its stored references (#116).

Feedback resolves the criteria of the JD it references; everything else has no reference and
runs bias-only. All ``db``-marked because the resolver reads persisted documents and criteria.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.engine.state import DriftReference
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.identity import User
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.services.drift_reference import resolve_drift_reference, resolve_jd_criteria

pytestmark = pytest.mark.db


def _manager(db_session: Session) -> User:
    user = User(
        external_user_id=f"drift-ref-{uuid.uuid4()}",
        legal_name="Drift Ref Manager",
        email=f"{uuid.uuid4()}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _jd_with_criteria(db_session: Session, owner: User, criteria: list[str]) -> Document:
    jd = Document(owner_id=owner.id, doc_type=DocType.jd, role_title="Analyst")
    db_session.add(jd)
    db_session.flush()
    for position, text in enumerate(criteria):
        db_session.add(JdCriterion(jd_document_id=jd.id, text=text, position=position))
    db_session.flush()
    return jd


def test_feedback_resolves_its_referenced_jd_criteria_in_order(db_session: Session) -> None:
    owner = _manager(db_session)
    jd = _jd_with_criteria(db_session, owner, ["Python proficiency", "Clear market view"])
    feedback = Document(owner_id=owner.id, doc_type=DocType.feedback, reference_jd_id=jd.id)
    db_session.add(feedback)
    db_session.flush()

    reference = resolve_drift_reference(db_session, feedback)

    assert reference == DriftReference(reference_text="Python proficiency\nClear market view")


def test_feedback_without_a_referenced_jd_has_no_reference(db_session: Session) -> None:
    owner = _manager(db_session)
    feedback = Document(owner_id=owner.id, doc_type=DocType.feedback)
    db_session.add(feedback)
    db_session.flush()

    assert resolve_drift_reference(db_session, feedback) is None


def test_feedback_whose_jd_has_no_criteria_has_no_reference(db_session: Session) -> None:
    owner = _manager(db_session)
    jd = _jd_with_criteria(db_session, owner, [])
    feedback = Document(owner_id=owner.id, doc_type=DocType.feedback, reference_jd_id=jd.id)
    db_session.add(feedback)
    db_session.flush()

    assert resolve_drift_reference(db_session, feedback) is None


def test_a_jd_has_no_reference_of_its_own(db_session: Session) -> None:
    owner = _manager(db_session)
    jd = _jd_with_criteria(db_session, owner, ["Python proficiency"])

    assert resolve_drift_reference(db_session, jd) is None


def test_promotion_has_no_reference_until_peer_feedback_wiring(db_session: Session) -> None:
    owner = _manager(db_session)
    promotion = Document(owner_id=owner.id, doc_type=DocType.promotion)
    db_session.add(promotion)
    db_session.flush()

    assert resolve_drift_reference(db_session, promotion) is None


def test_resolve_jd_criteria_returns_texts_in_position_order(db_session: Session) -> None:
    owner = _manager(db_session)
    jd = Document(owner_id=owner.id, doc_type=DocType.jd)
    db_session.add(jd)
    db_session.flush()
    db_session.add(JdCriterion(jd_document_id=jd.id, text="second", position=1))
    db_session.add(JdCriterion(jd_document_id=jd.id, text="first", position=0))
    db_session.flush()

    assert resolve_jd_criteria(db_session, jd_document_id=jd.id) == ["first", "second"]
