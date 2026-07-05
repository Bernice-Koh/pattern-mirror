"""Stage 1 of the engine: the Dictionary Service, a deterministic Module (no LLM).

Region-scoped active rules are matched against a document's lemmas; each match becomes
a ``CandidateFlag`` carrying a verbatim span and full provenance (rule, citation,
category) for the later stages to verify and persist. Loading and matching are
split so the matcher is a pure function over plain rules: region and active scoping are
applied once at the DB boundary (``load_active_rules``), and the matcher trusts what it
is given. Persisting the resulting flags and the analyze endpoint are owned by #21.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.tokenisation import lemmatise_with_offsets
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import BiasCategory, FlagSourceStage


@dataclass(frozen=True)
class DictionaryRule:
    """A dictionary entry reduced to what matching needs: no ORM, no session, no I/O."""

    id: uuid.UUID
    lemma_key: str
    category: BiasCategory
    citation_id: uuid.UUID
    explanation: str
    recommended_alternatives: tuple[str, ...]


def load_active_rules(session: Session, region_code: str) -> list[DictionaryRule]:
    """Load active dictionary rules scoped to ``region_code`` as plain value objects.

    The region filter and the active filter are applied here, at the DB boundary, so the
    matcher can trust that every rule it receives is in scope for the document.

    Args:
        session: An open database session.
        region_code: The jurisdiction whose lexicon applies (``"SG"`` for the MVP).

    Returns:
        The region's active rules; empty if the region has no active lexicon.
    """
    entries = session.scalars(
        select(Dictionary).where(
            Dictionary.region_code == region_code,
            Dictionary.active.is_(True),
        )
    ).all()
    return [
        DictionaryRule(
            id=entry.id,
            lemma_key=entry.lemma_key,
            category=entry.category,
            citation_id=entry.citation_id,
            explanation=entry.explanation,
            recommended_alternatives=tuple(entry.recommended_alternatives),
        )
        for entry in entries
    ]


def load_category_citations(session: Session, region_code: str) -> dict[BiasCategory, uuid.UUID]:
    """Map each category in the active lexicon to a representative TAFEP citation.

    This is the citation floor a contextual flag attaches (ADR 0006: every flag carries a
    citation by reference, never the model's word). A contextual flag of category X reuses
    the curated TAFEP citation that an active dictionary entry of X already cites. A category
    with no active entry has no floor, and the Contextual Pass suppresses flags it cannot
    cite rather than surfacing them uncited.

    Args:
        session: An open database session.
        region_code: The jurisdiction whose lexicon applies (``"SG"`` for the MVP).

    Returns:
        One citation id per category present in the region's active lexicon.
    """
    rows = session.execute(
        select(Dictionary.category, Dictionary.citation_id).where(
            Dictionary.region_code == region_code,
            Dictionary.active.is_(True),
        )
    ).all()
    floor: dict[BiasCategory, uuid.UUID] = {}
    for category, citation_id in rows:
        floor.setdefault(category, citation_id)
    return floor


def match_dictionary(text: str, rules: Sequence[DictionaryRule]) -> list[CandidateFlag]:
    """Flag every span of ``text`` whose lemmas match an active dictionary rule.

    Matching is leftmost-longest and non-overlapping: at each position the longest rule
    that matches wins and its tokens are consumed before scanning resumes. A ``lemma_key``
    shared by several rules (one phrase coded under more than one category) yields one
    flag per rule. Spans are sliced from the unmodified source, so each ``raw_span`` is
    verbatim and survives the Adjudicator's later check.

    Args:
        text: The raw document text, matched and spanned without modification.
        rules: Region-scoped active rules, e.g. from ``load_active_rules``.

    Returns:
        Candidate flags in document order, each with its span offsets and provenance.
    """
    if not rules:
        return []

    rules_by_key: dict[str, list[DictionaryRule]] = {}
    for rule in rules:
        rules_by_key.setdefault(rule.lemma_key, []).append(rule)
    longest_phrase = max(key.count(" ") + 1 for key in rules_by_key)

    tokens = lemmatise_with_offsets(text)
    flags: list[CandidateFlag] = []
    position = 0
    while position < len(tokens):
        matched_length = 0
        for length in range(min(longest_phrase, len(tokens) - position), 0, -1):
            window = tokens[position : position + length]
            key = " ".join(token.lemma for token in window)
            matched_rules = rules_by_key.get(key)
            if matched_rules is None:
                continue
            start, end = window[0].start, window[-1].end
            raw_span = text[start:end]
            flags.extend(
                CandidateFlag(
                    source_stage=FlagSourceStage.dictionary,
                    category=rule.category,
                    raw_span=raw_span,
                    start_offset=start,
                    end_offset=end,
                    citation_id=rule.citation_id,
                    dictionary_entry_id=rule.id,
                    explanation=rule.explanation,
                    lemma_key=key,
                    recommended_alternatives=rule.recommended_alternatives,
                )
                for rule in matched_rules
            )
            matched_length = length
            break
        position += matched_length or 1
    return flags
