"""Document-scoped endpoints: the draft lifecycle (create, restore, autosave, submit) and
the manual re-check (design spec §12).

The lifecycle handlers are thin and synchronous (CRUD, not the analysis path): each calls one
owner-scoped service function and serialises the result, so no ORM object crosses the API. The
re-check streams, so it is async — ``POST /documents/{doc_id}/recheck`` clears the document's
active dismissals, then streams a fresh engine run so every flag, including ones a prior run
dismissal-suppressed, surfaces again. The Judge gate and verdict suppression still apply;
re-check resets dismissals only. Like ``/analyze/stream``, it carries the current text in the
body (so it rides ahead of autosave) and uses SSE for the one-directional stream.
"""

import uuid
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.api.schemas import FlagResponse, serialise_flag
from pattern_mirror.api.sse import format_sse
from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.db.session import get_session
from pattern_mirror.engine.llm_agent import build_instructor_client
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AnalysisTrigger, DocType, DocumentStatus
from pattern_mirror.models.identity import User
from pattern_mirror.services.documents import (
    create_draft,
    get_draft,
    list_documents,
    list_flags,
    resolve_feedback_context,
    resolve_promotion_context,
    submit_document,
    update_draft,
)
from pattern_mirror.services.drift_reference import resolve_drift_reference
from pattern_mirror.services.interactions import deactivate_document_dismissals
from pattern_mirror.services.jd_criteria import (
    draft_jd_criteria,
    list_jd_criteria,
    replace_jd_criteria,
)
from pattern_mirror.services.run_registry import get_run_registry
from pattern_mirror.services.streaming_analysis import stream_analysis_events

router = APIRouter(tags=["documents"])


class CreateDocumentRequest(BaseModel):
    """The type of a new draft to create."""

    doc_type: DocType


class UpdateDraftRequest(BaseModel):
    """An autosave: the draft's current title and text."""

    title: str | None = None
    content: str


class SubmitRequest(BaseModel):
    """The final text captured when a draft is submitted."""

    content: str


class DocumentResponse(BaseModel):
    """A document's persisted state, returned to the editor on create, restore, and write."""

    id: uuid.UUID
    doc_type: DocType
    title: str | None
    status: DocumentStatus
    content: str


def _serialise_document(document: Document) -> DocumentResponse:
    """Map the ORM document into its response model (no ORM leaks out)."""
    return DocumentResponse(
        id=document.id,
        doc_type=document.doc_type,
        title=document.title,
        status=document.status,
        content=document.content,
    )


class DocumentSummaryResponse(BaseModel):
    """A document's metadata for the history listing — no text, just what a row shows."""

    id: uuid.UUID
    doc_type: DocType
    title: str | None
    role_title: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


def _serialise_document_summary(document: Document) -> DocumentSummaryResponse:
    """Map an ORM document to its listing summary; content stays out of the list payload."""
    return DocumentSummaryResponse(
        id=document.id,
        doc_type=document.doc_type,
        title=document.title,
        role_title=document.role_title,
        status=document.status,
        created_at=document.created_at,
        updated_at=document.updated_at,
        submitted_at=document.submitted_at,
    )


class FeedbackContextResponse(BaseModel):
    """The reference context the Feedback Checkpoint surface renders above the editor:
    the candidate and role, and the JD criteria the note's drift check is measured against."""

    role_title: str | None
    subject_id: uuid.UUID | None
    subject_name: str | None
    criteria: list[str]


@router.get("/documents", summary="List the current user's documents")
def list_my_documents(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DocumentSummaryResponse]:
    """Return the current manager's own documents, newest first."""
    documents = list_documents(session, owner_id=current_user.id)
    return [_serialise_document_summary(document) for document in documents]


@router.post("/documents", summary="Create a draft document")
def create_document(
    request: CreateDocumentRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    """Create an empty draft owned by the current user and return it."""
    document = create_draft(session, owner_id=current_user.id, doc_type=request.doc_type)
    return _serialise_document(document)


@router.get("/documents/{doc_id}", summary="Fetch a document by id")
def get_document(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    """Return the owner's document so the editor can restore its draft on load."""
    document = get_draft(session, document_id=doc_id, owner_id=current_user.id)
    return _serialise_document(document)


@router.get(
    "/documents/{doc_id}/flags",
    summary="List a document's latest-run bias flags",
)
def get_document_flags(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[FlagResponse]:
    """Return the owner's latest-run, surfaced flags so a reopened surface re-hydrates without a
    fresh engine run (the reason a submitted document shows its flags at all, and a draft skips the
    contextual re-run on open)."""
    flags = list_flags(session, document_id=doc_id, owner_id=current_user.id)
    return [serialise_flag(flag) for flag in flags]


@router.get(
    "/documents/{doc_id}/feedback-context",
    summary="Read a feedback document's criteria bar and context chips",
)
def get_feedback_context(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeedbackContextResponse:
    """Return the candidate, role, and reference JD criteria for the checkpoint surface."""
    context = resolve_feedback_context(session, document_id=doc_id, owner_id=current_user.id)
    return FeedbackContextResponse(
        role_title=context.role_title,
        subject_id=context.subject_id,
        subject_name=context.subject_name,
        criteria=context.criteria,
    )


class PeerCorroborationItem(BaseModel):
    """One rubric criterion and whether the employee's peers evidence it, with the peer quote."""

    criterion: str
    corroborated: bool
    evidence: str | None


class PromotionContextResponse(BaseModel):
    """The reference context the Promotion Writeup surface renders above the editor: the employee
    and target level, the rubric the writeup's drift check is measured against, and what peers say
    for each criterion (the corroborating evidence, #121)."""

    role_title: str | None
    subject_id: uuid.UUID | None
    subject_name: str | None
    criteria: list[str]
    corroboration: list[PeerCorroborationItem]


@router.get(
    "/documents/{doc_id}/promotion-context",
    summary="Read a promotion document's rubric bar, context chips, and peer corroboration",
)
def get_promotion_context(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PromotionContextResponse:
    """Return the employee, target level, rubric, and peer corroboration for the writeup surface."""
    context = resolve_promotion_context(session, document_id=doc_id, owner_id=current_user.id)
    return PromotionContextResponse(
        role_title=context.role_title,
        subject_id=context.subject_id,
        subject_name=context.subject_name,
        criteria=context.criteria,
        corroboration=[
            PeerCorroborationItem(
                criterion=item.criterion,
                corroborated=item.corroborated,
                evidence=item.evidence,
            )
            for item in context.corroboration
        ],
    )


class DraftJdCriteriaRequest(BaseModel):
    """The JD's current text to draft criteria from (carried in the body, ahead of autosave)."""

    content: str


class ConfirmJdCriteriaRequest(BaseModel):
    """The manager-confirmed criteria to persist as the JD's drift reference."""

    criteria: list[str]


class JdCriteriaResponse(BaseModel):
    """A JD's criteria — drafted (unconfirmed) or confirmed, depending on the endpoint."""

    criteria: list[str]


@router.get(
    "/documents/{doc_id}/jd-criteria",
    summary="Read a JD's confirmed criteria",
)
def get_jd_criteria(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JdCriteriaResponse:
    """Return the JD's confirmed criteria so the confirm step can pre-fill an edited set."""
    criteria = list_jd_criteria(session, document_id=doc_id, owner_id=current_user.id)
    return JdCriteriaResponse(criteria=criteria)


@router.post(
    "/documents/{doc_id}/jd-criteria/draft",
    summary="Draft a JD's criteria from its text with the extraction agent",
)
def draft_criteria(
    doc_id: uuid.UUID,
    request: DraftJdCriteriaRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JdCriteriaResponse:
    """Draft criteria for the manager to review; persists only an audit row, not the drafts."""
    settings = get_settings()
    client = build_instructor_client(settings)
    criteria = draft_jd_criteria(
        session,
        document_id=doc_id,
        owner_id=current_user.id,
        jd_text=request.content,
        client=client,
        model=settings.analysis_model,
    )
    return JdCriteriaResponse(criteria=criteria)


@router.put(
    "/documents/{doc_id}/jd-criteria",
    summary="Confirm a JD's criteria, replacing its set",
)
def confirm_criteria(
    doc_id: uuid.UUID,
    request: ConfirmJdCriteriaRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JdCriteriaResponse:
    """Persist the manager-confirmed criteria as the JD's drift reference (idempotent replace)."""
    criteria = replace_jd_criteria(
        session,
        document_id=doc_id,
        owner_id=current_user.id,
        texts=request.criteria,
    )
    return JdCriteriaResponse(criteria=criteria)


@router.patch("/documents/{doc_id}", summary="Autosave a draft's text")
def update_document(
    doc_id: uuid.UUID,
    request: UpdateDraftRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    """Persist an autosave of the draft's title and content. Runs no analysis."""
    document = update_draft(
        session,
        document_id=doc_id,
        owner_id=current_user.id,
        title=request.title,
        content=request.content,
    )
    return _serialise_document(document)


@router.post(
    "/documents/{doc_id}/submit",
    summary="Submit a draft, capturing its final text",
)
def submit(
    doc_id: uuid.UUID,
    request: SubmitRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    """Transition the draft to submitted, capturing the final text alongside its flags."""
    document = submit_document(
        session,
        document_id=doc_id,
        owner_id=current_user.id,
        content=request.content,
    )
    return _serialise_document(document)


class RecheckRequest(BaseModel):
    """A request to re-check a document against its current text."""

    content: str


@router.post(
    "/documents/{doc_id}/recheck",
    summary="Clear a document's dismissals and stream a fresh engine run",
    response_class=StreamingResponse,
)
async def recheck_document(
    doc_id: uuid.UUID,
    request: RecheckRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Validate ownership, then stream a run that first clears the document's dismissals.

    The dismissal-clearing write and the stream run in the same generator so all session
    use stays on one thread: ``get_session`` is a sync dependency and the response body is
    streamed from a threadpool, so mutating the session in the async handler would touch it
    across threads (the Session is not thread-safe). Mirrors ``/analyze/stream``.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = session.get(Document, doc_id)
    if document is None or document.owner_id != current_user.id:
        raise DocumentNotFoundError(doc_id)

    registry = get_run_registry()
    client = build_instructor_client(get_settings())
    drift_reference = resolve_drift_reference(session, document)

    def event_source() -> Iterator[bytes]:
        deactivate_document_dismissals(session, document.id)
        session.commit()
        for event in stream_analysis_events(
            session,
            document_id=document.id,
            content=request.content,
            doc_type=document.doc_type,
            registry=registry,
            contextual_client=client,
            judge_client=client,
            recommendations_client=client,
            drift_client=client if drift_reference is not None else None,
            drift_reference=drift_reference,
            trigger=AnalysisTrigger.recheck,
        ):
            yield format_sse(event)

    return StreamingResponse(event_source(), media_type="text/event-stream")
