"""The 3-of-4 gate over the four growth Agents' verdicts (design spec §3).

A phrase advances to the pending-additions queue only when at least three of the four Agents
favour it AND the Citation agent found support — a missing citation blocks dictionary inclusion
regardless of the other votes. This module is pure: it reads the parsed Agent results and
decides; persistence lives in ``services.dictionary_growth``.
"""

from dataclasses import dataclass

from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    ProposerResult,
    SkepticResult,
)
from pattern_mirror.models.enums import BiasCategory, FlagScope

GROWTH_AGREEMENT_THRESHOLD = 3


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
    """Apply the 3-of-4 gate with the citation-required override to the four Agent results.

    A vote in favour is: the Proposer supports inclusion, the Skeptic's honest verdict supports
    it, the Categorizer scopes it 'general', and the Citation agent found support. The phrase
    advances only when at least three of these hold and a citation was found.

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
    votes_in_favour = sum(
        (
            proposer.supports_inclusion,
            skeptic.supports_inclusion,
            categorizer.scope is FlagScope.general,
            has_citation,
        )
    )
    advance = has_citation and votes_in_favour >= GROWTH_AGREEMENT_THRESHOLD
    return GrowthVerdict(
        advance=advance,
        votes_in_favour=votes_in_favour,
        proposed_category=proposer.category,
        scope=categorizer.scope,
        has_citation=has_citation,
    )
