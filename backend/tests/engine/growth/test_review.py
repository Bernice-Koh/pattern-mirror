"""The 3-of-4 gate: agreement counting and the citation-required override.

Pure logic over the four parsed Agent results — no client, no database.
"""

from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    FoundCitation,
    ProposerResult,
    SkepticResult,
)
from pattern_mirror.engine.growth.review import evaluate_gate
from pattern_mirror.models.enums import BiasCategory, CitationSourceType, FlagScope


def _proposer(
    supports: bool = True, category: BiasCategory = BiasCategory.gender
) -> ProposerResult:
    return ProposerResult(supports_inclusion=supports, category=category, reasoning="r")


def _skeptic(supports: bool = True) -> SkepticResult:
    return SkepticResult(supports_inclusion=supports, reasoning="r")


def _categorizer(scope: FlagScope = FlagScope.general) -> CategorizerResult:
    return CategorizerResult(scope=scope, reasoning="r")


def _citation(found: bool = True) -> CitationResult:
    source = (
        FoundCitation(
            source_type=CitationSourceType.academic,
            title="t",
            reference="ref",
            publication_year=2020,
            finding="f",
        )
        if found
        else None
    )
    return CitationResult(found_support=found, citation=source, reasoning="r")


def test_all_four_in_favour_advances() -> None:
    verdict = evaluate_gate(_proposer(), _skeptic(), _categorizer(), _citation())

    assert verdict.advance is True
    assert verdict.votes_in_favour == 4
    assert verdict.proposed_category is BiasCategory.gender
    assert verdict.scope is FlagScope.general
    assert verdict.has_citation is True


def test_three_of_four_advances() -> None:
    # Skeptic dissents; Proposer, Categorizer, and Citation carry it to three.
    verdict = evaluate_gate(_proposer(), _skeptic(supports=False), _categorizer(), _citation())

    assert verdict.advance is True
    assert verdict.votes_in_favour == 3


def test_two_of_four_does_not_advance() -> None:
    verdict = evaluate_gate(
        _proposer(), _skeptic(supports=False), _categorizer(FlagScope.role_specific), _citation()
    )

    assert verdict.advance is False
    assert verdict.votes_in_favour == 2


def test_no_citation_blocks_even_when_the_other_three_agree() -> None:
    # Proposer, Skeptic, and Categorizer all favour it, but a missing citation is a hard block.
    verdict = evaluate_gate(_proposer(), _skeptic(), _categorizer(), _citation(found=False))

    assert verdict.advance is False
    assert verdict.votes_in_favour == 3
    assert verdict.has_citation is False


def test_proposed_category_comes_from_the_proposer() -> None:
    verdict = evaluate_gate(
        _proposer(category=BiasCategory.age), _skeptic(), _categorizer(), _citation()
    )

    assert verdict.proposed_category is BiasCategory.age
