"""The ``CandidateFlag`` value object that flows between engine stages.

Produced by the Dictionary Service (Stage 1) and the Contextual Pass (Stage 2),
verified by the Adjudicator (Stage 3), then persisted by the analyze endpoint. A plain
frozen dataclass: it carries a span plus provenance, but no validation and no DB
mapping. Field optionality mirrors the nullable columns on the ``flags`` table, which
is the durable record for flags from every stage, so this shape persists without rework.
"""

import uuid
from dataclasses import dataclass

from pattern_mirror.models.enums import BiasCategory, FlagSourceStage, Severity


@dataclass(frozen=True)
class CandidateFlag:
    """One in-memory bias detection: a source span plus its full provenance.

    The dictionary stage populates every field. Fields that a later stage may not know
    (offsets a contextual flag only gains at adjudication; a dictionary rule or its
    citation, absent on LLM-only flags) are optional, matching the ``flags`` table.
    """

    source_stage: FlagSourceStage
    category: BiasCategory
    severity: Severity
    raw_span: str
    start_offset: int | None = None
    end_offset: int | None = None
    citation_id: uuid.UUID | None = None
    dictionary_entry_id: uuid.UUID | None = None
    explanation: str | None = None
    lemma_key: str | None = None
