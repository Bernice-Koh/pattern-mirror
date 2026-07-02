"""The typed working set that flows through the LangGraph engine, plus its channels.

One ``EngineState`` object carries a run end-to-end; nodes read it and return partial
``StateUpdate`` dicts that the graph merges per channel. Postgres is the durable source of
truth — this is the per-run working set, not a record.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated, TypedDict

import structlog

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.models.enums import DocType, FlagVerdict

_log = structlog.get_logger("pattern_mirror.engine.state")


def accumulate_candidate_flags(
    existing: list[CandidateFlag], new: list[CandidateFlag]
) -> list[CandidateFlag]:
    """Reducer for the candidate-flag channel: append, so each stage adds to the others.

    Provenance is not recomputed here — it rides on each flag's ``source_stage``, so the
    accumulated list records which stage produced which flag.
    """
    return existing + new


@dataclass(frozen=True)
class JudgeScore:
    """The Judge's verdict on one surviving flag: its confidence and whether the gate dropped it.

    ``confidence`` is the raw verbalized score in [0, 1] (ADR-0008), or None for a deterministic
    dictionary flag the Judge does not score. ``suppressed`` is True when the calibrated score
    fell below the threshold: the flag is logged but not surfaced and gets no recommendation.
    """

    flag: CandidateFlag
    confidence: float | None
    suppressed: bool = False


@dataclass(frozen=True)
class FlagRecommendation:
    """The Recommendations Agent's rewrites for one above-threshold flag.

    ``alternatives`` is always 2-3 phrasings (never one "correct" answer, design spec §7),
    and ``rationale`` is grounded in the flag's citation. Produced only for surfaced
    contextual flags; the flag it concerns rides along so persistence can match it to its row.
    """

    flag: CandidateFlag
    rationale: str
    alternatives: list[str]


@dataclass(frozen=True)
class SuppressedFlag:
    """A verified flag an active dismissal suppresses, with the dismissal that did it.

    Produced by the suppression Module between the Adjudicator and the Judge: the flag is
    logged with ``suppressed=true`` and this reference, but is not scored, rewritten, or
    surfaced (design spec §12).
    """

    flag: CandidateFlag
    dismissal_id: uuid.UUID


@dataclass(frozen=True)
class DictionaryVerdict:
    """The Contextual Pass's GDOR ruling on one dictionary flag, keyed by its resolved span.

    Carried from the Contextual Pass to the Verdict node, which cannot reach back into the
    dictionary flags directly: the candidate-flag channel is append-only.
    """

    start_offset: int
    end_offset: int
    verdict: FlagVerdict
    reasoning: str


@dataclass(frozen=True)
class DriftReference:
    """The swapped reference corpus a drift run compares the document against.

    Present only on drift runs (feedback vs JD, promotion vs peer feedback); its shape
    firms up with the drift-check stage.
    """

    reference_text: str


@dataclass(frozen=True)
class DriftFinding:
    """Whether one reference criterion is addressed by the document, with its evidence.

    ``evidence`` is a span copied verbatim from the document and its resolved offsets, present
    only when ``addressed`` and the quote verified against the source; a non-verbatim quote is
    blanked (``evidence=None``) so a fabricated quote never surfaces, while the verdict stands.
    """

    criterion: str
    addressed: bool
    evidence: str | None
    evidence_start: int | None
    evidence_end: int | None


class EngineState(TypedDict):
    """The whole working set of one analysis run, as the graph's channel schema.

    Channels differ in how updates merge. ``candidate_flags`` *accumulates*: the
    dictionary and contextual stages each append, via ``accumulate_candidate_flags``.
    Every other channel *overwrites* (LangGraph's default last-value-wins): the Adjudicator
    replaces ``verified_flags`` with its survivors, the Verdict node overwrites it with the
    flags the Contextual Pass ruled ``unacceptable`` and fills ``verdict_suppressed_flags``,
    the suppression Module overwrites it again with the un-dismissed subset and fills
    ``dismissal_suppressed_flags``, the Judge replaces ``judge_scores``, and Recommendations
    replaces ``recommendations`` wholesale. ``dictionary_verdicts`` carries the Contextual
    Pass's rulings forward to the Verdict node. The drift check runs as its own stage, reading
    ``drift_reference`` and writing ``drift_findings``. The identity and inputs
    (``analysis_run_id``, ``document_id``, ``document_text``, ``doc_type``, ``region_code``)
    are set at init and not changed.
    """

    analysis_run_id: uuid.UUID
    document_id: uuid.UUID
    document_text: str
    doc_type: DocType
    region_code: str
    candidate_flags: Annotated[list[CandidateFlag], accumulate_candidate_flags]
    dictionary_verdicts: list[DictionaryVerdict]
    verified_flags: list[CandidateFlag]
    verdict_suppressed_flags: list[CandidateFlag]
    dismissal_suppressed_flags: list[SuppressedFlag]
    judge_scores: list[JudgeScore]
    recommendations: list[FlagRecommendation]
    drift_reference: DriftReference | None
    drift_findings: list[DriftFinding]


class StateUpdate(TypedDict, total=False):
    """A node's partial return: only the channels it changed, merged into ``EngineState``.

    Total-false because a node returns a subset; the inputs and identity are init-only and
    so are absent here.
    """

    candidate_flags: list[CandidateFlag]
    dictionary_verdicts: list[DictionaryVerdict]
    verified_flags: list[CandidateFlag]
    verdict_suppressed_flags: list[CandidateFlag]
    dismissal_suppressed_flags: list[SuppressedFlag]
    judge_scores: list[JudgeScore]
    recommendations: list[FlagRecommendation]
    drift_reference: DriftReference | None
    drift_findings: list[DriftFinding]


def initial_state(
    *,
    analysis_run_id: uuid.UUID,
    document_id: uuid.UUID,
    document_text: str,
    doc_type: DocType,
    region_code: str,
    drift_reference: DriftReference | None = None,
) -> EngineState:
    """Build the starting state for a run: identity and inputs set, channels empty."""
    return EngineState(
        analysis_run_id=analysis_run_id,
        document_id=document_id,
        document_text=document_text,
        doc_type=doc_type,
        region_code=region_code,
        candidate_flags=[],
        dictionary_verdicts=[],
        verified_flags=[],
        verdict_suppressed_flags=[],
        dismissal_suppressed_flags=[],
        judge_scores=[],
        recommendations=[],
        drift_reference=drift_reference,
        drift_findings=[],
    )


def log_transition(stage: str, document_id: uuid.UUID, update: StateUpdate) -> None:
    """Log the delta a node contributes, keyed by document id, for the engine audit trail.

    Args:
        stage: The node that produced the update.
        document_id: The run's document, the correlation key for the audit trail.
        update: The partial update the node returned, whose channels are the delta.
    """
    delta_sizes = {
        channel: len(value) for channel, value in update.items() if isinstance(value, list)
    }
    _log.info(
        "engine.transition",
        stage=stage,
        document_id=str(document_id),
        channels=sorted(update),
        delta_sizes=delta_sizes,
    )
