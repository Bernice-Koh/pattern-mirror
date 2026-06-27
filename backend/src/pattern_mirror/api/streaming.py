"""The /analyze/stream endpoint: stream the full engine run as Server-Sent Events.

Layer 2 of JD Studio's two-trigger model (design spec §3, §12). The client opens this
after a typing pause; the backend drives the engine and streams flags as each stage
verifies them. SSE (not WebSocket) because the stream is one-directional server -> client.
The handler is thin: it validates ownership, then translates the streaming service's domain
events into SSE frames — the engine and persistence logic stay in ``services``.

The transport is POST (not native ``EventSource``) so the current document text rides in
the body and the client can abort the stream with an ``AbortSignal`` when typing resumes.
"""

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.api.schemas import serialise_flag
from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.db.session import get_session
from pattern_mirror.engine.llm_agent import build_instructor_client
from pattern_mirror.models.documents import Document
from pattern_mirror.models.identity import User
from pattern_mirror.services.run_registry import get_run_registry
from pattern_mirror.services.streaming_analysis import (
    FlagSurfaced,
    RunCompleted,
    StageCompleted,
    StreamEvent,
    stream_analysis_events,
)

router = APIRouter(tags=["analyze"])


class AnalyzeStreamRequest(BaseModel):
    """A request to stream the full engine run over an existing document's current text."""

    document_id: uuid.UUID
    content: str


class StageEventData(BaseModel):
    """Payload of a ``stage`` event: a pipeline stage completed."""

    stage: str


class DoneEventData(BaseModel):
    """Payload of the terminal ``done`` event."""

    analysis_run_id: uuid.UUID
    status: str
    flag_count: int


def _format_sse(event: StreamEvent) -> bytes:
    """Render one streaming domain event as an SSE frame (``event:``/``data:`` lines)."""
    name: str
    payload: BaseModel
    match event:
        case StageCompleted(stage=stage):
            name, payload = "stage", StageEventData(stage=stage)
        case FlagSurfaced(flag=flag):
            name, payload = "flag", serialise_flag(flag)
        case RunCompleted(analysis_run_id=run_id, status=status, flag_count=count):
            name, payload = (
                "done",
                DoneEventData(analysis_run_id=run_id, status=status.value, flag_count=count),
            )
    return f"event: {name}\ndata: {payload.model_dump_json()}\n\n".encode()


@router.post(
    "/analyze/stream",
    summary="Stream the full engine run for a document as Server-Sent Events",
    response_class=StreamingResponse,
)
async def analyze_stream(
    request: AnalyzeStreamRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Validate ownership, then stream the engine run for the document's current text.

    Raises:
        DocumentNotFoundError: if the document is absent or owned by another user.
    """
    document = session.get(Document, request.document_id)
    if document is None or document.owner_id != current_user.id:
        raise DocumentNotFoundError(request.document_id)

    registry = get_run_registry()
    # Built here (network-free) and injected, so the engine layer stays free of settings;
    # None when no key is configured, which runs the dictionary-only path. One client drives
    # both Agent stages — the model is chosen per call.
    client = build_instructor_client(get_settings())

    def event_source() -> Iterator[bytes]:
        for event in stream_analysis_events(
            session,
            document_id=document.id,
            content=request.content,
            doc_type=document.doc_type,
            registry=registry,
            contextual_client=client,
            judge_client=client,
        ):
            yield _format_sse(event)

    return StreamingResponse(event_source(), media_type="text/event-stream")
