"""Resolving a document's drift reference from its stored references (#116, #120).

Feedback resolves the criteria of the JD it references; promotion resolves its employee's peer
feedback; anything unlinked has no reference and runs bias-only. All ``db``-marked because the
resolver reads persisted documents, criteria, and peer feedback.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.engine.state import DriftReference
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType, SubjectType
from pattern_mirror.models.identity import Subject, User
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.models.peer_feedback import PeerFeedback
from pattern_mirror.models.promotion_rubric import PromotionRubricCriterion
from pattern_mirror.services.drift_reference import (
    resolve_drift_reference,
    resolve_jd_criteria,
    resolve_peer_feedback,
    resolve_promotion_rubric,
)

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


def _employee(db_session: Session) -> Subject:
    subject = Subject(subject_type=SubjectType.employee, legal_name="Drift Ref Employee")
    db_session.add(subject)
    db_session.flush()
    return subject


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


def test_promotion_resolves_its_employees_peer_feedback(db_session: Session) -> None:
    owner = _manager(db_session)
    employee = _employee(db_session)
    for author, position in [("Peer A", 0), ("Peer B", 1)]:
        db_session.add(
            PeerFeedback(
                subject_id=employee.id,
                author_label=author,
                strengths="s",
                development="d",
                overall="o",
                position=position,
            )
        )
    promotion = Document(owner_id=owner.id, doc_type=DocType.promotion, subject_id=employee.id)
    db_session.add(promotion)
    db_session.flush()

    reference = resolve_drift_reference(db_session, promotion)

    assert reference is not None
    assert reference.reference_text.startswith("Peer A\n")
    # Peers are separated so the drift agent reads distinct voices, in stated order.
    assert "\n\nPeer B\n" in reference.reference_text


def test_promotion_without_peer_feedback_has_no_reference(db_session: Session) -> None:
    owner = _manager(db_session)
    employee = _employee(db_session)
    promotion = Document(owner_id=owner.id, doc_type=DocType.promotion, subject_id=employee.id)
    db_session.add(promotion)
    db_session.flush()

    assert resolve_drift_reference(db_session, promotion) is None


def test_promotion_without_a_subject_has_no_reference(db_session: Session) -> None:
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


def test_resolve_peer_feedback_folds_each_peer_into_a_labelled_block(db_session: Session) -> None:
    employee = _employee(db_session)
    db_session.add(
        PeerFeedback(
            subject_id=employee.id,
            author_label="Squad engineer",
            strengths="Owns the architecture",
            development="Delegate more",
            overall="Ready",
            position=0,
        )
    )
    db_session.flush()

    assert resolve_peer_feedback(db_session, subject_id=employee.id) == [
        "Squad engineer\n"
        "Strengths: Owns the architecture\n"
        "Development: Delegate more\n"
        "Overall: Ready"
    ]


def test_resolve_peer_feedback_orders_peers_by_position(db_session: Session) -> None:
    employee = _employee(db_session)
    for author, position in [("second", 1), ("first", 0)]:
        db_session.add(
            PeerFeedback(
                subject_id=employee.id,
                author_label=author,
                strengths="s",
                development="d",
                overall="o",
                position=position,
            )
        )
    db_session.flush()

    blocks = resolve_peer_feedback(db_session, subject_id=employee.id)
    labels = [block.split("\n", 1)[0] for block in blocks]
    assert labels == ["first", "second"]


def test_resolve_promotion_rubric_returns_texts_in_position_order(db_session: Session) -> None:
    level = f"Director — {uuid.uuid4()}"
    db_session.add(PromotionRubricCriterion(level_label=level, text="second", position=1))
    db_session.add(PromotionRubricCriterion(level_label=level, text="first", position=0))
    db_session.flush()

    assert resolve_promotion_rubric(db_session, level_label=level) == ["first", "second"]


def test_resolve_promotion_rubric_is_scoped_to_its_level(db_session: Session) -> None:
    level = f"Director — {uuid.uuid4()}"
    other = f"Director — {uuid.uuid4()}"
    db_session.add(PromotionRubricCriterion(level_label=level, text="owns delivery", position=0))
    db_session.add(PromotionRubricCriterion(level_label=other, text="other level", position=0))
    db_session.flush()

    assert resolve_promotion_rubric(db_session, level_label=level) == ["owns delivery"]


def test_resolve_promotion_rubric_is_empty_for_an_unknown_level(db_session: Session) -> None:
    assert resolve_promotion_rubric(db_session, level_label="Director — Unseeded") == []


def test_peer_feedback_blocks_join_into_a_single_reference_text(db_session: Session) -> None:
    # The #120 contract: an employee's rows resolve to one reference corpus with no engine change.
    employee = _employee(db_session)
    for position in range(3):
        db_session.add(
            PeerFeedback(
                subject_id=employee.id,
                author_label=f"peer-{position}",
                strengths="s",
                development="d",
                overall="o",
                position=position,
            )
        )
    db_session.flush()

    corpus = "\n\n".join(resolve_peer_feedback(db_session, subject_id=employee.id))

    assert corpus.count("peer-") == 3
    assert isinstance(corpus, str)
