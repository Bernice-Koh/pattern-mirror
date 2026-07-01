"""review_candidate runs the four agents, logs every argument, and gates on 3-of-4.

The Anthropic calls are replaced by a fake keyed on the requested schema, so one fake serves
all four agents offline (CONVENTIONS). Persistence is asserted against the test database.
"""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.growth.agents import (
    CategorizerResult,
    CitationResult,
    FoundCitation,
    ProposerResult,
    SkepticResult,
)
from pattern_mirror.engine.growth.review import GrowthCandidate
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import AgentName, BiasCategory, CitationSourceType, FlagScope
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.dictionary_growth import review_candidate

pytestmark = pytest.mark.db


class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeCompletion:
    def __init__(self, usage: _FakeUsage) -> None:
        self.usage = usage


class _FakeGrowthClient:
    """One fake for all four agents: returns the result registered for the requested schema."""

    def __init__(self, results: dict[type, Any]) -> None:
        self._results = results
        self._completion = _FakeCompletion(_FakeUsage(200, 60))
        self.calls: list[dict[str, Any]] = []

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        self.calls.append(kwargs)
        return self._results[kwargs["response_model"]], self._completion


def _settings() -> Settings:
    return Settings(app_env="test", database_url="postgresql+psycopg://unused")


def _found_citation() -> FoundCitation:
    return FoundCitation(
        source_type=CitationSourceType.academic,
        title="Bias in hiring language",
        reference="doi:10.1000/x",
        publication_year=2019,
        finding="Coded phrasing deters applicants.",
    )


def _results(
    *,
    proposer_supports: bool = True,
    skeptic_supports: bool = True,
    scope: FlagScope = FlagScope.general,
    citation_found: bool = True,
    category: BiasCategory = BiasCategory.gender,
) -> dict[type, Any]:
    return {
        ProposerResult: ProposerResult(
            supports_inclusion=proposer_supports, category=category, reasoning="for"
        ),
        SkepticResult: SkepticResult(supports_inclusion=skeptic_supports, reasoning="against"),
        CategorizerResult: CategorizerResult(scope=scope, reasoning="scope"),
        CitationResult: CitationResult(
            found_support=citation_found,
            citation=_found_citation() if citation_found else None,
            reasoning="search",
        ),
    }


def _candidate() -> GrowthCandidate:
    return GrowthCandidate(
        phrase="cultural fit",
        lemma_key="cultural fit",
        example_excerpts=["looking for a strong cultural fit", "must be a cultural fit"],
    )


def test_advance_writes_proposal_agent_runs_citation_and_pending(db_session: Session) -> None:
    client = _FakeGrowthClient(_results())

    outcome = review_candidate(
        db_session, client=client, candidate=_candidate(), settings=_settings()
    )

    assert outcome.advanced is True
    assert outcome.votes_in_favour == 4
    assert outcome.pending_addition_id is not None

    proposal = db_session.get(DictionaryProposal, outcome.proposal_id)
    assert proposal is not None
    assert proposal.citation_id is not None

    citation = db_session.get(Citation, proposal.citation_id)
    assert citation is not None
    assert citation.reference == "doi:10.1000/x"

    runs = db_session.scalars(
        select(AgentRun).where(AgentRun.proposal_id == outcome.proposal_id)
    ).all()
    assert {run.agent_name for run in runs} == {
        AgentName.proposer,
        AgentName.skeptic,
        AgentName.categorizer,
        AgentName.citation,
    }

    pending = db_session.get(PendingDictionaryAddition, outcome.pending_addition_id)
    assert pending is not None
    assert pending.proposed_category is BiasCategory.gender
    assert pending.proposal_id == outcome.proposal_id


def test_sub_threshold_logs_arguments_but_creates_no_pending(db_session: Session) -> None:
    # Only Proposer and Citation favour it: two votes, below the gate.
    client = _FakeGrowthClient(_results(skeptic_supports=False, scope=FlagScope.role_specific))

    outcome = review_candidate(
        db_session, client=client, candidate=_candidate(), settings=_settings()
    )

    assert outcome.advanced is False
    assert outcome.votes_in_favour == 2
    assert outcome.pending_addition_id is None

    runs = db_session.scalars(
        select(AgentRun).where(AgentRun.proposal_id == outcome.proposal_id)
    ).all()
    assert len(runs) == 4
    pending = db_session.scalars(
        select(PendingDictionaryAddition).where(
            PendingDictionaryAddition.proposal_id == outcome.proposal_id
        )
    ).all()
    assert pending == []


def test_no_citation_blocks_and_persists_no_citation(db_session: Session) -> None:
    # The other three agree, but no citation is a hard block and no Citation row is written.
    client = _FakeGrowthClient(_results(citation_found=False))

    outcome = review_candidate(
        db_session, client=client, candidate=_candidate(), settings=_settings()
    )

    assert outcome.advanced is False
    assert outcome.votes_in_favour == 3
    assert outcome.pending_addition_id is None

    proposal = db_session.get(DictionaryProposal, outcome.proposal_id)
    assert proposal is not None
    assert proposal.citation_id is None


def test_every_agent_output_is_parsed_before_any_record(db_session: Session) -> None:
    # The boundary: each recorded output is the schema-parsed result, not raw text.
    client = _FakeGrowthClient(_results())

    outcome = review_candidate(
        db_session, client=client, candidate=_candidate(), settings=_settings()
    )

    proposer_run = db_session.scalars(
        select(AgentRun).where(
            AgentRun.proposal_id == outcome.proposal_id,
            AgentRun.agent_name == AgentName.proposer,
        )
    ).one()
    assert proposer_run.output["category"] == BiasCategory.gender.value
    assert proposer_run.output["supports_inclusion"] is True
    assert proposer_run.input["phrase"] == "cultural fit"
