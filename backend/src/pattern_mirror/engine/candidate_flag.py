"""The ``CandidateFlag`` value object that flows between engine stages.

Produced by the Dictionary Service (Stage 1) and the Contextual Pass (Stage 2),
verified by the Adjudicator (Stage 3), then persisted by the analyze endpoint. A plain
frozen dataclass: it carries a span plus provenance, but no validation and no DB
mapping. Field optionality mirrors the nullable columns on the ``flags`` table, which
is the durable record for flags from every stage, so this shape persists without rework.
"""

import uuid
from dataclasses import dataclass

from pattern_mirror.models.enums import BiasCategory, FlagScope, FlagSourceStage, FlagVerdict


@dataclass(frozen=True)
class CandidateFlag:
    """One in-memory bias detection: a source span plus its full provenance.

    The dictionary stage populates every field. Fields a later stage may not know are
    optional, matching the nullable columns on the ``flags`` table: offsets a contextual
    flag only gains at adjudication, and a dictionary rule, its citation, and a lemma key
    are all absent on LLM-only contextual flags.

    ``scope`` distinguishes *general* (dictionary-eligible) from *role-specific* (LLM-only)
    candidates — the trigger input for the Dictionary Growth loop (design spec §3). The
    dictionary stage produces only general flags, so it is the default. ``verdict`` is the
    Contextual Pass's GDOR ruling; ``None`` until that stage rules on the flag.
    """

    source_stage: FlagSourceStage
    category: BiasCategory
    raw_span: str
    scope: FlagScope = FlagScope.general
    start_offset: int | None = None
    end_offset: int | None = None
    citation_id: uuid.UUID | None = None
    dictionary_entry_id: uuid.UUID | None = None
    explanation: str | None = None
    lemma_key: str | None = None
    verdict: FlagVerdict | None = None
    # Curated rewrites carried from a dictionary rule; empty for contextual flags (the
    # Recommendations Agent attaches theirs later).
    recommended_alternatives: tuple[str, ...] = ()
