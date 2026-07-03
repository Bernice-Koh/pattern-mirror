"""Resolve the drift reference corpus for a document from its stored references.

Feedback drifts against the criteria of the JD it references; promotion against an employee's
peer feedback. One resolver so the streaming endpoints attach drift the same way for every
surface, swapping only the corpus — the "swapped reference, not a new engine" guarantee (design
spec §3, §8) made a single call site. The peer-feedback corpus is wired into
``resolve_drift_reference`` for promotion in #120.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.engine.state import DriftReference
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.models.peer_feedback import PeerFeedback


def resolve_jd_criteria(session: Session, *, jd_document_id: uuid.UUID) -> list[str]:
    """Return a JD's criteria texts in stated order."""
    return list(
        session.scalars(
            select(JdCriterion.text)
            .where(JdCriterion.jd_document_id == jd_document_id)
            .order_by(JdCriterion.position)
        ).all()
    )


def resolve_peer_feedback(session: Session, *, subject_id: uuid.UUID) -> list[str]:
    """Return an employee's peer feedback as one labelled block per peer, in stated order.

    Each block folds the three free-text fields (§8) into prose the drift agent reads as a single
    peer voice; joining the blocks gives the promotion writeup's reference corpus.
    """
    rows = session.scalars(
        select(PeerFeedback)
        .where(PeerFeedback.subject_id == subject_id)
        .order_by(PeerFeedback.position)
    ).all()
    return [
        f"{row.author_label}\n"
        f"Strengths: {row.strengths}\n"
        f"Development: {row.development}\n"
        f"Overall: {row.overall}"
        for row in rows
    ]


def resolve_drift_reference(session: Session, document: Document) -> DriftReference | None:
    """Build a document's drift reference, or ``None`` when it has no corpus to check against.

    Feedback resolves the criteria of the JD it references; a JD, an unlinked feedback, or a
    feedback whose JD has no criteria has no reference and runs bias-only. Promotion's
    peer-feedback corpus is wired in #120.

    Args:
        session: An open session.
        document: The document about to be analysed.

    Returns:
        The reference corpus to drift-check against, or ``None`` to skip the drift stage.
    """
    if document.doc_type is not DocType.feedback or document.reference_jd_id is None:
        return None
    criteria = resolve_jd_criteria(session, jd_document_id=document.reference_jd_id)
    if not criteria:
        return None
    return DriftReference(reference_text="\n".join(criteria))
