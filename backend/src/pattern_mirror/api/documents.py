"""Document-scoped endpoints. For now: the manual re-check (design spec §12).

``POST /documents/{doc_id}/recheck`` gives the manager a clean pass after a major rewrite:
it clears the document's active dismissals, then streams a fresh engine run so every flag —
including ones a prior run dismissal-suppressed — surfaces again. The Judge gate and verdict
suppression still apply; re-check resets dismissals only.

Like ``/analyze/stream``, the transport is POST with the current text in the body (so it
rides ahead of autosave) and SSE for the one-directional server -> client stream.
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.api.sse import format_sse
from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.db.session import get_session
from pattern_mirror.engine.llm_agent import build_instructor_client
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AnalysisTrigger
from pattern_mirror.models.identity import User
from pattern_mirror.services.interactions import deactivate_document_dismissals
from pattern_mirror.services.run_registry import get_run_registry
from pattern_mirror.services.streaming_analysis import stream_analysis_events

router = APIRouter(tags=["documents"])


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
            trigger=AnalysisTrigger.recheck,
        ):
            yield format_sse(event)

    return StreamingResponse(event_source(), media_type="text/event-stream")
