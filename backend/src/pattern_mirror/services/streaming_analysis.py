"""The Layer-2 streaming path: drive the engine graph and emit events as stages complete.

The slow half of the two-trigger model (design spec §3, §12). Where ``analyze_document``
runs Stage 1 synchronously and returns once, this drives the compiled LangGraph engine
stage by stage and yields a domain event after each one, so the caller can stream flags to
the client as they are verified rather than after the whole run.

The function yields plain domain events, not response models or SSE bytes — the api layer
owns that translation, so this service stays free of HTTP concerns. Persistence is
per-stage and committed as it goes, so a run's flags survive even when the client
disconnects or a newer run supersedes it: every flag is logged, only surfacing is gated
(log-everything-suppress-in-UI). The graph currently runs its stages inline; when the LLM
stages (#48–#50) add multi-second calls, stage execution moves off the event loop.
"""

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.orchestrator import build_default_graph
from pattern_mirror.engine.state import initial_state
from pattern_mirror.models.documents import AnalysisRun
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType
from pattern_mirror.services.analysis import build_flag
from pattern_mirror.services.run_registry import RunRegistry

_REGION_CODE = "SG"
_log = structlog.get_logger("pattern_mirror.services.streaming_analysis")


@dataclass(frozen=True)
class StageCompleted:
    """A pipeline stage finished; progress for the client, even when it added no flags."""

    stage: str


@dataclass(frozen=True)
class FlagSurfaced:
    """A verified flag the client should render. Its citation loads on the live session."""

    flag: Flag


@dataclass(frozen=True)
class RunCompleted:
    """The terminal event: the run is done, superseded, or failed. Always emitted last."""

    analysis_run_id: uuid.UUID
    status: AnalysisRunStatus
    flag_count: int


StreamEvent = StageCompleted | FlagSurfaced | RunCompleted


def _persist_verified_flags(
    session: Session,
    *,
    run: AnalysisRun,
    document_id: uuid.UUID,
    content: str,
    verified_flags: list[CandidateFlag],
) -> list[Flag]:
    """Persist a stage's verified flags and return them with citations loaded."""
    persisted_ids: list[uuid.UUID] = []
    for candidate in verified_flags:
        flag = build_flag(
            document_id=document_id,
            analysis_run_id=run.id,
            candidate=candidate,
            content=content,
        )
        session.add(flag)
        session.flush()
        persisted_ids.append(flag.id)
    if not persisted_ids:
        return []
    return list(
        session.scalars(
            select(Flag)
            .where(Flag.id.in_(persisted_ids))
            .options(selectinload(Flag.citation), selectinload(Flag.dictionary_entry))
            .order_by(Flag.start_offset)
        ).all()
    )


def stream_analysis_events(
    session: Session,
    *,
    document_id: uuid.UUID,
    content: str,
    doc_type: DocType,
    registry: RunRegistry,
    region_code: str = _REGION_CODE,
) -> Iterator[StreamEvent]:
    """Run the engine over a document and yield an event per stage, then a terminal event.

    Persists a fresh ``AnalysisRun`` (trigger ``typing_pause``) and registers it as the
    current run for the document. Each stage's verified flags are persisted and committed
    immediately; flags are surfaced only while this run is still the current one, so a
    superseded run keeps logging but stops streaming. A stage failure is logged against the
    run, which is marked ``failed``, and the stream still closes with a terminal event.

    Args:
        session: An open session whose lifetime spans the whole stream (the caller owns
            it). Committed per stage so persistence survives a disconnect.
        document_id: The document being analysed; the supersede key.
        content: The current document text to analyse.
        doc_type: The document's type, from the persisted document.
        registry: The run registry that arbitrates supersede.
        region_code: The lexicon region; SG for the MVP.

    Yields:
        ``StageCompleted`` per stage, ``FlagSurfaced`` per verified flag, and exactly one
        terminal ``RunCompleted``.
    """
    run = AnalysisRun(
        document_id=document_id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        status=AnalysisRunStatus.running,
    )
    session.add(run)
    session.flush()
    registry.register(document_id, run.id)
    _log.info("analysis.stream_started", analysis_run_id=str(run.id), document_id=str(document_id))

    flag_count = 0
    final_status = AnalysisRunStatus.complete
    try:
        graph = build_default_graph(session)
        state = initial_state(
            analysis_run_id=run.id,
            document_id=document_id,
            document_text=content,
            doc_type=doc_type,
            region_code=region_code,
        )
        for chunk in graph.stream(state, stream_mode="updates"):
            superseded = False
            for stage_name, update in chunk.items():
                # In "updates" mode a node that writes no channel yields ``None``.
                surfaced = _persist_verified_flags(
                    session,
                    run=run,
                    document_id=document_id,
                    content=content,
                    verified_flags=(update or {}).get("verified_flags", []),
                )
                session.commit()

                if not registry.is_latest(document_id, run.id):
                    final_status = AnalysisRunStatus.superseded
                    superseded = True
                    break

                yield StageCompleted(stage=stage_name)
                for flag in surfaced:
                    flag_count += 1
                    yield FlagSurfaced(flag=flag)
            if superseded:
                break
    except Exception:
        final_status = AnalysisRunStatus.failed
        session.rollback()
        _log.exception("analysis.stream_failed", analysis_run_id=str(run.id))
    finally:
        registry.release(document_id, run.id)

    run.status = final_status
    run.completed_at = datetime.now(UTC)
    session.commit()
    _log.info(
        "analysis.stream_finished",
        analysis_run_id=str(run.id),
        status=final_status,
        flag_count=flag_count,
    )
    yield RunCompleted(analysis_run_id=run.id, status=final_status, flag_count=flag_count)
