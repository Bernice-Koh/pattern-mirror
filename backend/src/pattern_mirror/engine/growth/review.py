"""The advancement gate over the four growth Agents' verdicts (design spec §3).

A phrase advances to the pending-additions queue only when both eligibility gates pass — a
citation was found AND the Categorizer scoped it ``general`` — and at least one debater (the
Proposer or the Skeptic) supports inclusion. A missing citation or a role-specific scope each
block dictionary inclusion regardless of the other votes: a role-specific phrase stays a
context-only flag, and an uncited one breaks the "every entry cites a source" promise (ADR 0006).
This module is pure; persistence lives in ``services.dictionary_growth``.
"""

from dataclasses import dataclass

from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    ProposerResult,
    SkepticResult,
)
from pattern_mirror.models.enums import BiasCategory, FlagScope


@dataclass(frozen=True)
class GrowthCandidate:
    """A recurring, uncatalogued phrase the trigger (#88) hands to the review flow."""

    phrase: str
    lemma_key: str
    example_excerpts: list[str]


@dataclass(frozen=True)
class GrowthVerdict:
    """The gate's decision over the four Agent results, plus the fields persistence needs."""

    advance: bool
    votes_in_favour: int
    proposed_category: BiasCategory
    scope: FlagScope
    has_citation: bool


def _citation_found(citation: CitationResult) -> bool:
    """A citation counts only when the agent both claims support and returns the source."""
    return citation.found_support and citation.citation is not None


def evaluate_gate(
    proposer: ProposerResult,
    skeptic: SkepticResult,
    categorizer: CategorizerResult,
    citation: CitationResult,
) -> GrowthVerdict:
    """Decide whether the phrase advances, applying the two hard gates and the debater vote.

    A phrase advances only when a citation was found, the Categorizer scoped it ``general``, and
    at least one of the Proposer or Skeptic supports inclusion. ``votes_in_favour`` tallies how
    many of the four favoured it, for the audit trail — it does not itself decide the gate.

    Args:
        proposer: The Proposer's case and chosen category.
        skeptic: The Skeptic's verdict after arguing against.
        categorizer: The Categorizer's scope call.
        citation: The Citation agent's search outcome.

    Returns:
        The verdict, carrying the vote count, the proposed category, the scope, and whether a
        citation was found.
    """
    has_citation = _citation_found(citation)
    is_general = categorizer.scope is FlagScope.general
    votes_in_favour = sum(
        (proposer.supports_inclusion, skeptic.supports_inclusion, is_general, has_citation)
    )
    advance = (
        has_citation and is_general and (proposer.supports_inclusion or skeptic.supports_inclusion)
    )
    return GrowthVerdict(
        advance=advance,
        votes_in_favour=votes_in_favour,
        proposed_category=proposer.category,
        scope=categorizer.scope,
        has_citation=has_citation,
    )
