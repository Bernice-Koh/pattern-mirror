"""The Pattern Dashboard read endpoint: a manager's own significant patterns (#66, §2 View 3).

Thin and synchronous (read-only aggregation, not the analysis path): one call into the cached
Pattern Aggregator, scoped to the signed-in manager so the data stays manager-only (§13). The
statistics are done server-side; the response carries structured facts for #67 to render without
editorialising. HR aggregates are a separate, structurally-isolated layer (#70).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.core.config import get_settings
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import BiasCategory
from pattern_mirror.models.identity import User
from pattern_mirror.services.pattern_aggregator import (
    AdoptionTrendPoint,
    DecisionPattern,
    PatternMode,
    PatternReport,
    WritingPattern,
)
from pattern_mirror.services.pattern_cache import cached_pattern_report

router = APIRouter(tags=["patterns"])


class WritingPatternResponse(BaseModel):
    """A coded term correlating with subject gender, with its provenance for drill-down."""

    mode: PatternMode
    term: str
    category: BiasCategory
    dimension: str
    group_counts: dict[str, int]
    supporting_count: int
    p_value: float
    role_title: str | None
    document_ids: list[uuid.UUID]


class DecisionPatternResponse(BaseModel):
    """A bias category the manager adopts or rejects at a significantly different rate."""

    category: BiasCategory
    adopted_count: int
    rejected_count: int
    total_count: int
    adoption_rate: float
    p_value: float
    document_ids: list[uuid.UUID]


class AdoptionTrendPointResponse(BaseModel):
    """The manager's overall adoption rate within one calendar month (the "over time" view)."""

    period: str
    adopted_count: int
    total_count: int
    adoption_rate: float


class PatternReportResponse(BaseModel):
    """The dashboard payload: both gated pattern families plus the adoption trend."""

    writing_patterns: list[WritingPatternResponse]
    decision_patterns: list[DecisionPatternResponse]
    adoption_trend: list[AdoptionTrendPointResponse]


def _serialise_writing(pattern: WritingPattern) -> WritingPatternResponse:
    return WritingPatternResponse(
        mode=pattern.mode,
        term=pattern.term,
        category=pattern.category,
        dimension=pattern.dimension,
        group_counts=pattern.group_counts,
        supporting_count=pattern.supporting_count,
        p_value=pattern.p_value,
        role_title=pattern.role_title,
        document_ids=list(pattern.document_ids),
    )


def _serialise_decision(pattern: DecisionPattern) -> DecisionPatternResponse:
    return DecisionPatternResponse(
        category=pattern.category,
        adopted_count=pattern.adopted_count,
        rejected_count=pattern.rejected_count,
        total_count=pattern.total_count,
        adoption_rate=pattern.adoption_rate,
        p_value=pattern.p_value,
        document_ids=list(pattern.document_ids),
    )


def _serialise_trend(point: AdoptionTrendPoint) -> AdoptionTrendPointResponse:
    return AdoptionTrendPointResponse(
        period=point.period,
        adopted_count=point.adopted_count,
        total_count=point.total_count,
        adoption_rate=point.adoption_rate,
    )


def _serialise_report(report: PatternReport) -> PatternReportResponse:
    """Map the aggregator's value objects into the response model (no internal types leak out)."""
    return PatternReportResponse(
        writing_patterns=[_serialise_writing(pattern) for pattern in report.writing_patterns],
        decision_patterns=[_serialise_decision(pattern) for pattern in report.decision_patterns],
        adoption_trend=[_serialise_trend(point) for point in report.adoption_trend],
    )


@router.get("/patterns", summary="The current manager's significant patterns")
def get_patterns(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PatternReportResponse:
    """Return the manager's own writing and decision patterns, gated and cached."""
    report = cached_pattern_report(
        session,
        owner_id=current_user.id,
        threshold=get_settings().pattern_significance_threshold,
    )
    return _serialise_report(report)
