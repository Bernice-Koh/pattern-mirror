"""Firm-wide aggregate queries for the HR Portal (#70, design spec §5/§11/§13).

A deterministic Module that returns only aggregated figures across every manager — never an
individual's writing. The privacy boundary is structural: nothing here carries a document id, an
owner id, or any document text out of the layer, and any cell drawn from fewer than the minimum
number of distinct managers is dropped before it can re-identify someone. Effectiveness and the
dismiss-and-kept rate are computed from the same flag history the Pattern Aggregator reads (#66);
the gold-set calibration series comes from the persisted ``calibration_runs`` (#23).
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import BiasCategory, DocType
from pattern_mirror.services.behavioural_states import (
    ADOPTION_STATES,
    BehaviouralState,
    FlagOutcome,
    classify,
)
from pattern_mirror.services.calibration_runs import calibration_history
from pattern_mirror.services.flag_outcomes import surfaced_flag_groups


@dataclass(frozen=True)
class AdoptionByPeriod:
    """Firm-wide adoption rate within one calendar month (the "over time" view, §11)."""

    period: str
    adopted_count: int
    total_count: int
    adoption_rate: float


@dataclass(frozen=True)
class AdoptionByCategory:
    """Firm-wide adoption rate for one bias category."""

    category: BiasCategory
    adopted_count: int
    total_count: int
    adoption_rate: float


@dataclass(frozen=True)
class AdoptionByDocType:
    """Firm-wide adoption rate for one document type."""

    doc_type: DocType
    adopted_count: int
    total_count: int
    adoption_rate: float


@dataclass(frozen=True)
class EffectivenessReport:
    """Adoption broken down three ways — the effectiveness dimension (§11)."""

    adoption_over_time: tuple[AdoptionByPeriod, ...]
    adoption_by_category: tuple[AdoptionByCategory, ...]
    adoption_by_doc_type: tuple[AdoptionByDocType, ...]


@dataclass(frozen=True)
class GoldSetPoint:
    """One persisted gold-set calibration run: the metrics at the time it was measured."""

    recorded_at: datetime
    agreement: float | None
    ece: float | None
    brier: float | None
    scored_count: int


@dataclass(frozen=True)
class DismissKeptByCategory:
    """How often a category's flags were dismissed yet the language was kept (a trust signal)."""

    category: BiasCategory
    dismissed_and_kept_count: int
    total_count: int
    dismissed_and_kept_rate: float


@dataclass(frozen=True)
class CalibrationReport:
    """The calibration dimension: the gold-set series plus dismiss-and-kept by category (§11)."""

    gold_set_trend: tuple[GoldSetPoint, ...]
    dismissed_and_kept_by_category: tuple[DismissKeptByCategory, ...]


@dataclass(frozen=True)
class DictionaryHealthReport:
    """The dictionary-health dimension (§11). All fields are None until Dictionary Growth (#8)."""

    proposal_volume: int | None
    agent_agreement_rate: float | None
    citation_coverage: float | None
    approval_throughput: int | None


@dataclass(frozen=True)
class _ClassifiedFlag:
    """One surfaced flag firm-wide, reduced to the keys the dashboards group by and its outcome.

    ``owner_id`` is kept only to count distinct managers per cell for suppression; it never leaves
    the layer.
    """

    owner_id: uuid.UUID
    doc_type: DocType
    category: BiasCategory
    period: str | None
    state: BehaviouralState


def _firm_classified_flags(session: Session) -> list[_ClassifiedFlag]:
    """Classify every surfaced flag on every manager's submitted documents (§13 outcome)."""
    rows = session.execute(
        select(
            Document.id,
            Document.owner_id,
            Document.doc_type,
            Document.submitted_content,
            Document.submitted_at,
        ).where(Document.submitted_content.is_not(None))
    ).all()
    content_by_document: dict[uuid.UUID, str] = {}
    meta_by_document: dict[uuid.UUID, tuple[uuid.UUID, DocType, str | None]] = {}
    for doc_id, owner_id, doc_type, content, submitted_at in rows:
        if content is None:
            continue
        content_by_document[doc_id] = content
        period = submitted_at.strftime("%Y-%m") if submitted_at is not None else None
        meta_by_document[doc_id] = (owner_id, doc_type, period)

    classified: list[_ClassifiedFlag] = []
    for group in surfaced_flag_groups(session, list(content_by_document)):
        owner_id, doc_type, period = meta_by_document[group.document_id]
        state = classify(
            FlagOutcome(
                flagged_text=group.raw_span,
                interaction_kinds=group.interaction_kinds,
                final_text=content_by_document[group.document_id],
            )
        )
        classified.append(_ClassifiedFlag(owner_id, doc_type, group.category, period, state))
    return classified


def _adoption_cells[K: Hashable](
    classified: list[_ClassifiedFlag],
    key_of: Callable[[_ClassifiedFlag], K | None],
    min_cell_size: int,
) -> list[tuple[K, int, int]]:
    """Group flags by ``key_of``, returning ``(key, adopted, total)`` for cells above the floor.

    A cell drawn from fewer than ``min_cell_size`` distinct managers is dropped, so no figure can
    be traced back to one individual.
    """
    grouped: dict[K, list[_ClassifiedFlag]] = defaultdict(list)
    for item in classified:
        key = key_of(item)
        if key is not None:
            grouped[key].append(item)

    cells: list[tuple[K, int, int]] = []
    for key, items in grouped.items():
        if len({item.owner_id for item in items}) < min_cell_size:
            continue
        adopted = sum(1 for item in items if item.state in ADOPTION_STATES)
        cells.append((key, adopted, len(items)))
    return cells


def effectiveness_report(session: Session, *, min_cell_size: int) -> EffectivenessReport:
    """Firm-wide adoption over time, by category, and by document type (§11).

    Args:
        session: The active database session.
        min_cell_size: Minimum distinct managers a cell must cover, else it is suppressed.

    Returns:
        Adoption rates grouped three ways, each cell covering at least ``min_cell_size`` managers.
    """
    classified = _firm_classified_flags(session)
    over_time = _adoption_cells(classified, lambda item: item.period, min_cell_size)
    by_category = _adoption_cells(classified, lambda item: item.category, min_cell_size)
    by_doc_type = _adoption_cells(classified, lambda item: item.doc_type, min_cell_size)
    return EffectivenessReport(
        adoption_over_time=tuple(
            AdoptionByPeriod(period, adopted, total, adopted / total)
            for period, adopted, total in sorted(over_time, key=lambda cell: str(cell[0]))
        ),
        adoption_by_category=tuple(
            AdoptionByCategory(category, adopted, total, adopted / total)
            for category, adopted, total in sorted(by_category, key=lambda cell: str(cell[0]))
        ),
        adoption_by_doc_type=tuple(
            AdoptionByDocType(doc_type, adopted, total, adopted / total)
            for doc_type, adopted, total in sorted(by_doc_type, key=lambda cell: str(cell[0]))
        ),
    )


def _dismiss_kept_by_category(
    classified: list[_ClassifiedFlag], min_cell_size: int
) -> list[DismissKeptByCategory]:
    """Share of each category's flags dismissed but kept in the final text, small cells dropped."""
    by_category: dict[BiasCategory, list[_ClassifiedFlag]] = defaultdict(list)
    for item in classified:
        by_category[item.category].append(item)

    rows: list[DismissKeptByCategory] = []
    for category, items in by_category.items():
        if len({item.owner_id for item in items}) < min_cell_size:
            continue
        kept = sum(1 for item in items if item.state is BehaviouralState.dismissed_and_kept)
        rows.append(DismissKeptByCategory(category, kept, len(items), kept / len(items)))
    rows.sort(key=lambda row: row.category.value)
    return rows


def calibration_report(session: Session, *, min_cell_size: int) -> CalibrationReport:
    """The gold-set calibration series plus firm-wide dismiss-and-kept by category (§11).

    Args:
        session: The active database session.
        min_cell_size: Minimum distinct managers a dismiss-and-kept cell must cover.

    Returns:
        The persisted gold-set runs oldest-first and the suppressed dismiss-and-kept breakdown.
    """
    trend = tuple(
        GoldSetPoint(
            recorded_at=run.created_at,
            agreement=run.agreement,
            ece=run.ece,
            brier=run.brier,
            scored_count=run.scored_count,
        )
        for run in calibration_history(session)
    )
    classified = _firm_classified_flags(session)
    return CalibrationReport(
        gold_set_trend=trend,
        dismissed_and_kept_by_category=tuple(_dismiss_kept_by_category(classified, min_cell_size)),
    )


def dictionary_health_report(session: Session) -> DictionaryHealthReport:
    """The dictionary-health dimension. Empty until Dictionary Growth (#8) provides the data."""
    return DictionaryHealthReport(
        proposal_volume=None,
        agent_agreement_rate=None,
        citation_coverage=None,
        approval_throughput=None,
    )
