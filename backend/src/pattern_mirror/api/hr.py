"""The HR Portal's aggregate-only read endpoints (#70, design spec §11).

Three thin, synchronous, HR-gated handlers — one per §11 dimension — over the firm-wide aggregate
query layer. The response models carry only aggregated figures and their labels (period, category,
document type): no document id, no owner id, no document text. There is deliberately no route here
that returns an individual manager's writing, so the privacy boundary holds structurally (§5).
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import require_hr
from pattern_mirror.core.config import get_settings
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import BiasCategory, DocType
from pattern_mirror.services.hr_aggregates import (
    CalibrationReport,
    DictionaryHealthReport,
    EffectivenessReport,
    calibration_report,
    dictionary_health_report,
    effectiveness_report,
)

router = APIRouter(prefix="/hr", tags=["hr"], dependencies=[Depends(require_hr)])


class AdoptionByPeriodResponse(BaseModel):
    """Firm-wide adoption rate within one calendar month."""

    period: str
    adopted_count: int
    total_count: int
    adoption_rate: float


class AdoptionByCategoryResponse(BaseModel):
    """Firm-wide adoption rate for one bias category."""

    category: BiasCategory
    adopted_count: int
    total_count: int
    adoption_rate: float


class AdoptionByDocTypeResponse(BaseModel):
    """Firm-wide adoption rate for one document type."""

    doc_type: DocType
    adopted_count: int
    total_count: int
    adoption_rate: float


class EffectivenessResponse(BaseModel):
    """The effectiveness dimension: adoption over time, by category, by document type."""

    adoption_over_time: list[AdoptionByPeriodResponse]
    adoption_by_category: list[AdoptionByCategoryResponse]
    adoption_by_doc_type: list[AdoptionByDocTypeResponse]


class GoldSetPointResponse(BaseModel):
    """One persisted gold-set calibration run."""

    recorded_at: datetime
    agreement: float | None
    ece: float | None
    brier: float | None
    scored_count: int


class DismissKeptByCategoryResponse(BaseModel):
    """How often a category's flags were dismissed yet the language kept."""

    category: BiasCategory
    dismissed_and_kept_count: int
    total_count: int
    dismissed_and_kept_rate: float


class CalibrationResponse(BaseModel):
    """The calibration dimension: the gold-set series plus dismiss-and-kept by category."""

    gold_set_trend: list[GoldSetPointResponse]
    dismissed_and_kept_by_category: list[DismissKeptByCategoryResponse]


class DictionaryHealthResponse(BaseModel):
    """The dictionary-health dimension. All fields are null until Dictionary Growth (#8)."""

    proposal_volume: int | None
    agent_agreement_rate: float | None
    citation_coverage: float | None
    approval_throughput: int | None


def _serialise_effectiveness(report: EffectivenessReport) -> EffectivenessResponse:
    return EffectivenessResponse(
        adoption_over_time=[
            AdoptionByPeriodResponse(
                period=cell.period,
                adopted_count=cell.adopted_count,
                total_count=cell.total_count,
                adoption_rate=cell.adoption_rate,
            )
            for cell in report.adoption_over_time
        ],
        adoption_by_category=[
            AdoptionByCategoryResponse(
                category=cell.category,
                adopted_count=cell.adopted_count,
                total_count=cell.total_count,
                adoption_rate=cell.adoption_rate,
            )
            for cell in report.adoption_by_category
        ],
        adoption_by_doc_type=[
            AdoptionByDocTypeResponse(
                doc_type=cell.doc_type,
                adopted_count=cell.adopted_count,
                total_count=cell.total_count,
                adoption_rate=cell.adoption_rate,
            )
            for cell in report.adoption_by_doc_type
        ],
    )


def _serialise_calibration(report: CalibrationReport) -> CalibrationResponse:
    return CalibrationResponse(
        gold_set_trend=[
            GoldSetPointResponse(
                recorded_at=point.recorded_at,
                agreement=point.agreement,
                ece=point.ece,
                brier=point.brier,
                scored_count=point.scored_count,
            )
            for point in report.gold_set_trend
        ],
        dismissed_and_kept_by_category=[
            DismissKeptByCategoryResponse(
                category=row.category,
                dismissed_and_kept_count=row.dismissed_and_kept_count,
                total_count=row.total_count,
                dismissed_and_kept_rate=row.dismissed_and_kept_rate,
            )
            for row in report.dismissed_and_kept_by_category
        ],
    )


def _serialise_dictionary_health(report: DictionaryHealthReport) -> DictionaryHealthResponse:
    return DictionaryHealthResponse(
        proposal_volume=report.proposal_volume,
        agent_agreement_rate=report.agent_agreement_rate,
        citation_coverage=report.citation_coverage,
        approval_throughput=report.approval_throughput,
    )


@router.get("/effectiveness", summary="Firm-wide adoption trends (HR)")
def get_effectiveness(
    session: Annotated[Session, Depends(get_session)],
) -> EffectivenessResponse:
    """Adoption over time, by category, and by document type — aggregated across all managers."""
    report = effectiveness_report(session, min_cell_size=get_settings().hr_min_cell_size)
    return _serialise_effectiveness(report)


@router.get("/calibration", summary="Gold-set calibration and dismiss-and-kept trends (HR)")
def get_calibration(
    session: Annotated[Session, Depends(get_session)],
) -> CalibrationResponse:
    """The gold-set calibration series and the firm-wide dismiss-and-kept rate by category."""
    report = calibration_report(session, min_cell_size=get_settings().hr_min_cell_size)
    return _serialise_calibration(report)


@router.get("/dictionary-health", summary="Dictionary growth health (HR)")
def get_dictionary_health() -> DictionaryHealthResponse:
    """Dictionary-health metrics; an empty state until Dictionary Growth (#8) lands."""
    return _serialise_dictionary_health(dictionary_health_report())
