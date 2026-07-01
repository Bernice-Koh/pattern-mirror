"""Detect recurring, uncatalogued phrases the Contextual Pass keeps proposing (#88).

The dictionary grows from language managers actually use. When the Contextual Pass proposes the
same ``general`` phrase across enough distinct managers and documents — and it is neither already
catalogued nor already reviewed — it becomes a growth candidate for the four-agent flow (#89).
Role-specific proposals and one-offs never surface: the former stay context-only flags, the latter
are noise. Phrases are grouped by ``Flag.normalised_span``, which is the same Stage-1 lemma key the
dismissal fingerprint uses (#56), so trivial casing and inflection variants collapse together.

Read-only: this reports candidates, it does not persist anything. The job (``jobs.growth``) owns
running the review over them.
"""

from collections import Counter

import structlog
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.fingerprint import slice_sentence
from pattern_mirror.engine.growth.review import GrowthCandidate
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import FlagScope, FlagSourceStage
from pattern_mirror.models.growth import DictionaryProposal

_log = structlog.get_logger("pattern_mirror.services.growth_trigger")

# At most this many example sentences per candidate; the agents need a sense of usage, not the
# whole corpus, and the LLM prompt stays bounded regardless of how often a phrase recurs.
_MAX_EXCERPTS = 3


def find_growth_candidates(session: Session, settings: Settings) -> list[GrowthCandidate]:
    """Return the growth candidates whose recurrence clears the configured thresholds.

    A phrase qualifies when the Contextual Pass has proposed it, ``general`` and uncatalogued,
    across at least ``growth_recurrence_min_managers`` distinct managers and
    ``growth_recurrence_min_documents`` distinct documents, and it has not already been reviewed
    (no ``dictionary_proposals`` row) or catalogued (no active ``dictionaries`` row). Each candidate
    carries a representative surface form and up to three example sentences drawn from the documents
    it appeared in.

    Args:
        session: An open database session; nothing is written.
        settings: Source of the two recurrence thresholds.

    Returns:
        The qualifying candidates, ordered by lemma key for a deterministic batch.
    """
    catalogued = select(Dictionary.lemma_key).where(Dictionary.active.is_(True))
    already_reviewed = select(DictionaryProposal.lemma_key)

    recurring = (
        select(Flag.normalised_span)
        .join(Document, Flag.document_id == Document.id)
        .where(
            Flag.source_stage == FlagSourceStage.contextual,
            Flag.scope == FlagScope.general,
            Flag.normalised_span != "",
            Flag.normalised_span.not_in(catalogued),
            Flag.normalised_span.not_in(already_reviewed),
        )
        .group_by(Flag.normalised_span)
        .having(func.count(distinct(Document.owner_id)) >= settings.growth_recurrence_min_managers)
        .having(func.count(distinct(Flag.document_id)) >= settings.growth_recurrence_min_documents)
    )
    qualifying = set(session.scalars(recurring).all())
    if not qualifying:
        return []

    occurrences = session.execute(
        select(
            Flag.normalised_span,
            Flag.raw_span,
            Flag.start_offset,
            Flag.end_offset,
            Document.content,
        )
        .join(Document, Flag.document_id == Document.id)
        .where(
            Flag.source_stage == FlagSourceStage.contextual,
            Flag.scope == FlagScope.general,
            Flag.normalised_span.in_(qualifying),
        )
    ).all()

    surface_forms: dict[str, Counter[str]] = {key: Counter() for key in qualifying}
    excerpts: dict[str, list[str]] = {key: [] for key in qualifying}
    for lemma_key, raw_span, start, end, content in occurrences:
        surface_forms[lemma_key][raw_span] += 1
        excerpt = _excerpt(content, raw_span, start, end)
        if excerpt and excerpt not in excerpts[lemma_key]:
            excerpts[lemma_key].append(excerpt)

    candidates = [
        GrowthCandidate(
            phrase=_representative_form(surface_forms[key]),
            lemma_key=key,
            example_excerpts=sorted(excerpts[key])[:_MAX_EXCERPTS],
        )
        for key in sorted(qualifying)
    ]
    _log.info("growth.candidates_found", count=len(candidates))
    return candidates


def _excerpt(content: str, raw_span: str, start: int | None, end: int | None) -> str:
    """The sentence around the flagged span, or the raw span when offsets are absent."""
    if start is None or end is None:
        return raw_span
    return slice_sentence(content, start, end)


def _representative_form(forms: Counter[str]) -> str:
    """The most common surface form of a phrase; ties break lexicographically for determinism."""
    best_count = max(forms.values())
    return min(form for form, count in forms.items() if count == best_count)
