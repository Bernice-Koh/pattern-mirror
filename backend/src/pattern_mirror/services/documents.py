"""Document lifecycle service: create a draft, autosave it, submit it.

The CRUD half of a document's life, kept apart from the engine path in
``services.analysis``. Every function is owner-scoped — a missing or foreign document
raises ``DocumentNotFoundError`` — so the ownership rule lives in one place and handlers
stay thin. The caller owns the transaction (the request session commits on success);
these functions flush, never commit.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import DocType, DocumentStatus
from pattern_mirror.services.drift_reference import resolve_jd_criteria

_log = structlog.get_logger("pattern_mirror.services.documents")


def _owned_document(session: Session, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    document = session.get(Document, document_id)
    if document is None or document.owner_id != owner_id:
        raise DocumentNotFoundError(document_id)
    return document


def create_draft(session: Session, *, owner_id: uuid.UUID, doc_type: DocType) -> Document:
    """Create an empty draft for ``owner_id`` and return it.

    The editor creates the document up front, then analyses and autosaves against this one
    id, so an editing session maps to a single document rather than a row per keystroke.
    """
    document = Document(owner_id=owner_id, doc_type=doc_type)
    session.add(document)
    session.flush()
    _log.info("document.created", document_id=str(document.id), doc_type=doc_type.value)
    return document


def list_documents(session: Session, *, owner_id: uuid.UUID) -> list[Document]:
    """Return the owner's documents, newest first, for their document-history listing.

    Owner-scoped by the query, not the caller — the manager-only visibility boundary is
    structural, the same principle as the HR aggregate boundary (design spec §5). Ordered by
    ``created_at`` descending, backed by ``ix_documents_owner_id_created_at``.
    """
    return list(
        session.scalars(
            select(Document)
            .where(Document.owner_id == owner_id)
            .order_by(Document.created_at.desc())
        )
    )


def get_draft(session: Session, *, document_id: uuid.UUID, owner_id: uuid.UUID) -> Document:
    """Return the owner's document so the editor can restore it on load.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    return _owned_document(session, document_id, owner_id)


@dataclass(frozen=True)
class FeedbackContext:
    """What the Feedback Checkpoint surface shows above the editor: the candidate and role it
    is about, and the JD criteria the drift check measures the note against."""

    role_title: str | None
    subject_id: uuid.UUID | None
    subject_name: str | None
    criteria: list[str]


def resolve_feedback_context(
    session: Session, *, document_id: uuid.UUID, owner_id: uuid.UUID
) -> FeedbackContext:
    """Return the criteria bar and context chips for a feedback document's surface.

    Criteria resolve through the JD the feedback references (#116); an unlinked feedback returns
    an empty list and the surface renders bias-only.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = _owned_document(session, document_id, owner_id)
    criteria = (
        resolve_jd_criteria(session, jd_document_id=document.reference_jd_id)
        if document.reference_jd_id is not None
        else []
    )
    return FeedbackContext(
        role_title=document.role_title,
        subject_id=document.subject_id,
        subject_name=document.subject.legal_name if document.subject is not None else None,
        criteria=criteria,
    )


def update_draft(
    session: Session,
    *,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
    title: str | None,
    content: str,
) -> Document:
    """Persist an autosave: overwrite the draft's title and content. No engine run.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = _owned_document(session, document_id, owner_id)
    document.title = title
    document.content = content
    session.flush()
    return document


def submit_document(
    session: Session,
    *,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
    content: str,
) -> Document:
    """Transition the draft to submitted, snapshotting ``content`` as the final text.

    The final text rides in the request body (like re-check) so the submission captures
    exactly what the manager saw regardless of autosave timing. ``submitted_content`` is
    the version adoption is measured against (design spec §13); ``content`` is updated to
    match.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = _owned_document(session, document_id, owner_id)
    document.content = content
    document.submitted_content = content
    document.submitted_at = datetime.now(UTC)
    document.status = DocumentStatus.submitted
    session.flush()
    _log.info("document.submitted", document_id=str(document.id))
    return document
