"""Run the four-agent review over a growth candidate and persist the outcome (#89).

Orchestrates the Agents from ``engine.growth``: it writes one ``dictionary_proposals`` row per
candidate (so the arguments are logged even when the phrase fails to advance), records each
Agent's invocation to ``agent_runs``, persists the found citation, applies the 3-of-4 gate, and
queues a ``pending_dictionary_additions`` row when the phrase advances. Flushes but does not
commit — the caller (the growth job) owns the transaction.
"""

import uuid
from dataclasses import dataclass

import structlog
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.growth.agents import (
    GrowthAgentRun,
    run_categorizer,
    run_citation,
    run_proposer,
    run_skeptic,
)
from pattern_mirror.engine.growth.review import GrowthCandidate, evaluate_gate
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, estimate_cost_usd
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import AgentName
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.agent_runs import record_agent_run

_log = structlog.get_logger("pattern_mirror.services.dictionary_growth")


@dataclass(frozen=True)
class GrowthReviewOutcome:
    """What the review did with one candidate: its proposal, verdict, and any queue row."""

    proposal_id: uuid.UUID
    advanced: bool
    votes_in_favour: int
    pending_addition_id: uuid.UUID | None


def _record[R: BaseModel](
    session: Session,
    *,
    proposal_id: uuid.UUID,
    agent_name: AgentName,
    model: str,
    candidate: GrowthCandidate,
    run: GrowthAgentRun[R],
) -> AgentRun:
    return record_agent_run(
        session,
        agent_name=agent_name,
        model=model,
        input={"phrase": candidate.phrase, "excerpts": candidate.example_excerpts},
        output=run.result.model_dump(mode="json"),
        proposal_id=proposal_id,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        cost_usd=estimate_cost_usd(model, run.prompt_tokens, run.completion_tokens),
        latency_ms=run.latency_ms,
    )


def review_candidate(
    session: Session,
    *,
    client: StructuredCompletionClient,
    candidate: GrowthCandidate,
    settings: Settings,
) -> GrowthReviewOutcome:
    """Run the four Agents over ``candidate``, persist every argument, and gate on 3-of-4.

    Args:
        session: An open database session; the caller owns the transaction.
        client: An Instructor-wrapped Anthropic client (or a test fake); the model is chosen
            per Agent from ``settings``.
        candidate: The recurring phrase to evaluate, with its example excerpts.
        settings: Source of the per-Agent model choices (ADR 0012).

    Returns:
        The proposal id, whether the phrase advanced, its vote count, and the pending-addition
        id when it advanced.
    """
    proposal = DictionaryProposal(phrase=candidate.phrase, lemma_key=candidate.lemma_key)
    session.add(proposal)
    session.flush()

    proposer = run_proposer(
        client,
        phrase=candidate.phrase,
        excerpts=candidate.example_excerpts,
        model=settings.growth_proposer_model,
    )
    skeptic = run_skeptic(
        client,
        phrase=candidate.phrase,
        excerpts=candidate.example_excerpts,
        model=settings.growth_skeptic_model,
    )
    categorizer = run_categorizer(
        client,
        phrase=candidate.phrase,
        excerpts=candidate.example_excerpts,
        model=settings.growth_categorizer_model,
    )
    citation = run_citation(
        client,
        phrase=candidate.phrase,
        excerpts=candidate.example_excerpts,
        model=settings.growth_citation_model,
    )

    _record(
        session,
        proposal_id=proposal.id,
        agent_name=AgentName.proposer,
        model=settings.growth_proposer_model,
        candidate=candidate,
        run=proposer,
    )
    _record(
        session,
        proposal_id=proposal.id,
        agent_name=AgentName.skeptic,
        model=settings.growth_skeptic_model,
        candidate=candidate,
        run=skeptic,
    )
    _record(
        session,
        proposal_id=proposal.id,
        agent_name=AgentName.categorizer,
        model=settings.growth_categorizer_model,
        candidate=candidate,
        run=categorizer,
    )
    _record(
        session,
        proposal_id=proposal.id,
        agent_name=AgentName.citation,
        model=settings.growth_citation_model,
        candidate=candidate,
        run=citation,
    )

    verdict = evaluate_gate(proposer.result, skeptic.result, categorizer.result, citation.result)

    if verdict.has_citation:
        assert citation.result.citation is not None
        found = citation.result.citation
        row = Citation(
            source_type=found.source_type,
            title=found.title,
            reference=found.reference,
            publication_year=found.publication_year,
            finding=found.finding,
        )
        session.add(row)
        session.flush()
        proposal.citation_id = row.id

    pending_addition_id: uuid.UUID | None = None
    if verdict.advance:
        pending = PendingDictionaryAddition(
            proposal_id=proposal.id,
            phrase=candidate.phrase,
            lemma_key=candidate.lemma_key,
            proposed_category=verdict.proposed_category,
            explanation=proposer.result.reasoning,
            recommended_alternatives=proposer.result.recommended_alternatives,
        )
        session.add(pending)
        session.flush()
        pending_addition_id = pending.id

    _log.info(
        "growth.candidate_reviewed",
        proposal_id=str(proposal.id),
        phrase=candidate.phrase,
        advanced=verdict.advance,
        votes_in_favour=verdict.votes_in_favour,
        has_citation=verdict.has_citation,
        scope=verdict.scope.value,
    )
    return GrowthReviewOutcome(
        proposal_id=proposal.id,
        advanced=verdict.advance,
        votes_in_favour=verdict.votes_in_favour,
        pending_addition_id=pending_addition_id,
    )
