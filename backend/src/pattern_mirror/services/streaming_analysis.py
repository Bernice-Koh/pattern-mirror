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
from pattern_mirror.engine.llm_agent import StructuredCompletionClient
from pattern_mirror.engine.orchestrator import build_default_graph
from pattern_mirror.engine.state import (
    DriftReference,
    FlagRecommendation,
    JudgeScore,
    SuppressedFlag,
    initial_state,
)
from pattern_mirror.models.documents import AnalysisRun
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, AnalysisTrigger, DocType
from pattern_mirror.services.analysis import build_flag
from pattern_mirror.services.drift_findings import persist_drift_findings, reference_kind_for
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


def _persist_verdict_suppressed(
    session: Session,
    *,
    run: AnalysisRun,
    document_id: uuid.UUID,
    content: str,
    suppressed: list[CandidateFlag],
) -> None:
    """Persist each flag the Contextual Pass cleared (logged, not surfaced; ADR 0010).

    A keyword hit ruled a false positive or a justified requirement: written with its verdict
    and ``suppressed=True`` so only clear bias reaches the manager, while the Pattern Aggregator
    still sees the term fired.
    """
    for flag in suppressed:
        session.add(
            build_flag(
                document_id=document_id,
                analysis_run_id=run.id,
                candidate=flag,
                content=content,
                suppressed=True,
            )
        )
    session.flush()


def _persist_dismissal_suppressed(
    session: Session,
    *,
    run: AnalysisRun,
    document_id: uuid.UUID,
    content: str,
    suppressed: list[SuppressedFlag],
) -> None:
    """Persist each dismissal-suppressed flag with its dismissal reference (logged, not surfaced).

    These never reach the Judge or surface in the UI; they are written so the Pattern
    Aggregator still sees the flag fired and so suppression stays revisable (design spec §12).
    """
    for item in suppressed:
        session.add(
            build_flag(
                document_id=document_id,
                analysis_run_id=run.id,
                candidate=item.flag,
                content=content,
                suppressed=True,
                suppressed_by_dismissal_id=item.dismissal_id,
            )
        )
    session.flush()


def _persist_judge_scores(
    session: Session,
    *,
    run: AnalysisRun,
    document_id: uuid.UUID,
    content: str,
    scores: list[JudgeScore],
) -> tuple[list[Flag], dict[CandidateFlag, Flag]]:
    """Persist every scored flag (suppressed ones included) and return the surfaced ones.

    Log everything, suppress in UI: a below-threshold flag is written with ``suppressed=True``
    and its confidence, but is not returned for surfacing. The surfaced flags come back with
    citations loaded, in document order, alongside a map from each surfaced candidate to its
    persisted row so the Recommendations stage can attach rewrites to the right flag.
    """
    surfaced_ids: list[uuid.UUID] = []
    flag_by_candidate: dict[CandidateFlag, Flag] = {}
    for score in scores:
        flag = build_flag(
            document_id=document_id,
            analysis_run_id=run.id,
            candidate=score.flag,
            content=content,
            judge_confidence=score.confidence,
            suppressed=score.suppressed,
        )
        session.add(flag)
        session.flush()
        if not score.suppressed:
            surfaced_ids.append(flag.id)
            flag_by_candidate[score.flag] = flag
    if not surfaced_ids:
        return [], {}
    surfaced = list(
        session.scalars(
            select(Flag)
            .where(Flag.id.in_(surfaced_ids))
            .options(selectinload(Flag.citation), selectinload(Flag.dictionary_entry))
            .order_by(Flag.start_offset)
        ).all()
    )
    return surfaced, flag_by_candidate


def _attach_recommendations(
    flag_by_candidate: dict[CandidateFlag, Flag],
    recommendations: list[FlagRecommendation],
) -> None:
    """Write each recommendation set onto its surfaced flag row (the caller commits).

    Matched by the candidate the Judge persisted, so a rewrite lands on the exact flag it was
    generated for; a recommendation whose flag did not surface (a superseded run) is skipped.
    """
    for recommendation in recommendations:
        flag = flag_by_candidate.get(recommendation.flag)
        if flag is None:
            continue
        flag.recommendations = {
            "rationale": recommendation.rationale,
            "alternatives": recommendation.alternatives,
        }


def stream_analysis_events(
    session: Session,
    *,
    document_id: uuid.UUID,
    content: str,
    doc_type: DocType,
    registry: RunRegistry,
    contextual_client: StructuredCompletionClient | None = None,
    judge_client: StructuredCompletionClient | None = None,
    recommendations_client: StructuredCompletionClient | None = None,
    drift_client: StructuredCompletionClient | None = None,
    drift_reference: DriftReference | None = None,
    trigger: AnalysisTrigger = AnalysisTrigger.typing_pause,
    region_code: str = _REGION_CODE,
) -> Iterator[StreamEvent]:
    """Run the engine over a document and yield an event per stage, then a terminal event.

    Persists a fresh ``AnalysisRun`` and registers it as the
    current run for the document. Verdict-suppressed flags are persisted at the Verdict stage
    and dismissal-suppressed ones at the suppression stage; the rest at the Judge stage
    carrying their confidence and suppression, committed
    immediately, but un-suppressed flags surface only at the Recommendations stage, each
    carrying the rewrites generated for it — so the
    client renders a flag together with its alternatives rather than mutating it later. Both
    happen only while this run is still the current one: a superseded run keeps logging every
    flag and its rewrites but stops streaming. A stage failure is logged against the run, which
    is marked ``failed``, and the stream still closes with a terminal event.

    Args:
        session: An open session whose lifetime spans the whole stream (the caller owns
            it). Committed per stage so persistence survives a disconnect.
        document_id: The document being analysed; the supersede key.
        content: The current document text to analyse.
        doc_type: The document's type, from the persisted document.
        registry: The run registry that arbitrates supersede.
        contextual_client: The Contextual Pass client; ``None`` runs dictionary-only.
        judge_client: The Judge client; ``None`` passes every flag through ungated.
        recommendations_client: The Recommendations client; ``None`` surfaces flags with no
            rewrites.
        drift_client: The drift-check client; ``None`` skips the drift stage. Supplied with a
            ``drift_reference`` by the Feedback Checkpoint / Promotion Writeup surfaces.
        drift_reference: The reference corpus to drift-check against; ``None`` runs no drift stage.
        trigger: What started this run; ``recheck`` for a manual clean pass, otherwise the
            default typing pause.
        region_code: The lexicon region; SG for the MVP.

    Yields:
        ``StageCompleted`` per stage, ``FlagSurfaced`` per un-suppressed flag, and exactly
        one terminal ``RunCompleted``.
    """
    run = AnalysisRun(
        document_id=document_id,
        trigger=trigger,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        status=AnalysisRunStatus.running,
    )
    session.add(run)
    session.flush()
    registry.register(document_id, run.id)
    _log.info("analysis.stream_started", analysis_run_id=str(run.id), document_id=str(document_id))

    flag_count = 0
    final_status = AnalysisRunStatus.complete
    superseded = False
    try:
        graph = build_default_graph(
            session,
            contextual_client=contextual_client,
            judge_client=judge_client,
            recommendations_client=recommendations_client,
            drift_client=drift_client,
        )
        state = initial_state(
            analysis_run_id=run.id,
            document_id=document_id,
            document_text=content,
            doc_type=doc_type,
            region_code=region_code,
            drift_reference=drift_reference,
        )
        pending_surface: list[Flag] = []
        flag_by_candidate: dict[CandidateFlag, Flag] = {}
        for chunk in graph.stream(state, stream_mode="updates"):
            for stage_name, update in chunk.items():
                # In "updates" mode a node that writes no channel yields ``None``. Flags are
                # persisted when the Judge stage carries ``judge_scores`` but held back, then
                # surfaced at the Recommendations stage with the rewrites attached there.
                data = update or {}
                if "verdict_suppressed_flags" in data:
                    _persist_verdict_suppressed(
                        session,
                        run=run,
                        document_id=document_id,
                        content=content,
                        suppressed=data["verdict_suppressed_flags"],
                    )
                if "dismissal_suppressed_flags" in data:
                    _persist_dismissal_suppressed(
                        session,
                        run=run,
                        document_id=document_id,
                        content=content,
                        suppressed=data["dismissal_suppressed_flags"],
                    )
                if "judge_scores" in data:
                    pending_surface, flag_by_candidate = _persist_judge_scores(
                        session,
                        run=run,
                        document_id=document_id,
                        content=content,
                        scores=data["judge_scores"],
                    )
                if stage_name == "recommendations":
                    _attach_recommendations(flag_by_candidate, data.get("recommendations", []))
                if "drift_findings" in data:
                    # Drift is its own stage after the bias pipeline; persisted like a suppressed
                    # flag (log everything), read back by the surfaces rather than streamed here.
                    persist_drift_findings(
                        session,
                        run=run,
                        document_id=document_id,
                        reference_kind=reference_kind_for(doc_type),
                        findings=data["drift_findings"],
                    )
                session.commit()

                # Supersede gates surfacing, not persistence: a newer run stops this one's
                # stream but the engine keeps persisting every flag (log everything).
                if not superseded and not registry.is_latest(document_id, run.id):
                    superseded = True
                    final_status = AnalysisRunStatus.superseded
                if superseded:
                    continue

                yield StageCompleted(stage=stage_name)
                if stage_name == "recommendations":
                    for flag in pending_surface:
                        flag_count += 1
                        yield FlagSurfaced(flag=flag)
                    pending_surface = []
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
