"""Response models shared across the analysis endpoints, plus their serialisation.

A persisted ``Flag`` is rendered identically whether it leaves the synchronous
``/analyze`` endpoint or the streaming pipeline, so the response shape and the ORM ->
response mapping live here once and both routers import them. Keeping the mapping in the
api layer is what stops an ORM object from crossing the boundary.
"""

import uuid

from pydantic import BaseModel

from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    BiasCategory,
    CitationSourceType,
    FlagSourceStage,
    Severity,
)


class CitationResponse(BaseModel):
    """The verifiable source backing a flag."""

    source_type: CitationSourceType
    title: str
    reference: str
    publication_year: int | None
    finding: str | None


class FlagResponse(BaseModel):
    """One persisted flag with its provenance and citation."""

    id: uuid.UUID
    source_stage: FlagSourceStage
    category: BiasCategory
    severity: Severity
    raw_span: str
    start_offset: int
    end_offset: int
    explanation: str
    citation: CitationResponse


def serialise_flag(flag: Flag) -> FlagResponse:
    """Map a persisted flag and its relationships into the response model.

    Args:
        flag: A persisted flag whose dictionary entry and citation are loadable on the
            active session (so its severity and citation can be rendered).

    Returns:
        The flag as a boundary-safe response model.
    """
    # A persisted dictionary flag always has offsets, a rule (for severity), and a citation.
    assert flag.dictionary_entry is not None and flag.citation is not None
    assert flag.start_offset is not None and flag.end_offset is not None
    return FlagResponse(
        id=flag.id,
        source_stage=flag.source_stage,
        category=flag.category,
        severity=flag.dictionary_entry.severity,
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
    )
