"""Server-Sent Events framing shared by the streaming analysis endpoints.

Both the typing-pause stream (``/analyze/stream``) and the manual re-check
(``/documents/{id}/recheck``) drive the same engine and emit the same domain events, so the
translation from a ``StreamEvent`` into an SSE frame lives here once rather than per router.
"""

import uuid

from pydantic import BaseModel

from pattern_mirror.api.schemas import serialise_flag
from pattern_mirror.services.streaming_analysis import (
    FlagSurfaced,
    RunCompleted,
    StageCompleted,
    StreamEvent,
)


class StageEventData(BaseModel):
    """Payload of a ``stage`` event: a pipeline stage completed."""

    stage: str


class DoneEventData(BaseModel):
    """Payload of the terminal ``done`` event."""

    analysis_run_id: uuid.UUID
    status: str
    flag_count: int


def format_sse(event: StreamEvent) -> bytes:
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
