"""Response models shared across the analysis endpoints, plus their serialisation.

A persisted ``Flag`` is rendered identically whether it leaves the synchronous
``/analyze`` endpoint or the streaming pipeline, so the response shape and the ORM ->
response mapping live here once and both routers import them. Keeping the mapping in the
api layer is what stops an ORM object from crossing the boundary.
"""

import uuid

from pydantic import BaseModel

from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import BiasCategory, CitationSourceType, FlagSourceStage


class CitationResponse(BaseModel):
    """The verifiable source backing a flag."""

    source_type: CitationSourceType
    title: str
    reference: str
    publication_year: int | None
    finding: str | None


class RecommendationResponse(BaseModel):
    """Evidence-anchored rewrites for a flag: 2-3 alternatives and the rationale behind them."""

    rationale: str
    alternatives: list[str]


class FlagResponse(BaseModel):
    """One persisted flag with its provenance and citation.

    Every flag carries a citation by reference (ADR 0006): a dictionary flag cites its
    rule's source, a contextual flag the category-level TAFEP citation. No flag is surfaced
    uncited. ``recommendations`` is null until the Recommendations Agent attaches rewrites,
    and on flags it never runs on (dictionary, below threshold).
    """

    id: uuid.UUID
    source_stage: FlagSourceStage
    category: BiasCategory
    raw_span: str
    start_offset: int
    end_offset: int
    explanation: str
    citation: CitationResponse
    recommendations: RecommendationResponse | None


def serialise_flag(flag: Flag) -> FlagResponse:
    """Map a persisted flag and its relationships into the response model.

    Args:
        flag: A persisted flag whose citation relationship is loadable on the active session.

    Returns:
        The flag as a boundary-safe response model.
    """
    # Every persisted flag has resolved offsets (the Adjudicator) and a citation (ADR 0006).
    assert flag.start_offset is not None and flag.end_offset is not None
    assert flag.citation is not None
    return FlagResponse(
        id=flag.id,
        source_stage=flag.source_stage,
        category=flag.category,
        raw_span=flag.raw_span,
        start_offset=flag.start_offset,
        end_offset=flag.end_offset,
        explanation=flag.rationale["explanation"],
        citation=CitationResponse(
            source_type=flag.citation.source_type,
            title=flag.citation.title,
            reference=flag.citation.reference,
            publication_year=flag.citation.publication_year,
            finding=flag.citation.finding,
        ),
        recommendations=(
            RecommendationResponse(**flag.recommendations)
            if flag.recommendations is not None
            else None
        ),
    )
