"""Reconstruct a dictionary-growth entry's full provenance chain (#91).

Read-only assembly over what the growth loop already persists: the proposal, each of the four
agents' arguments (``agent_runs.proposal_id``), the found citation, the HR decision (the queued
addition's status), and the live dictionary row an approval created. Answers "where did this rule
come from?" months later. This module never mutates — the audit-defensibility guarantee (§4).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import ProposalNotFoundError
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import AgentName
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition

# The four growth agents run and record in this order; agent_runs share a transaction timestamp
# (Postgres now() is constant per transaction), so we order by role here, not by created_at.
_AGENT_ORDER = {
    AgentName.proposer: 0,
    AgentName.skeptic: 1,
    AgentName.categorizer: 2,
    AgentName.citation: 3,
}


@dataclass(frozen=True)
class ProposalAudit:
    """One growth entry's reconstructed chain: proposal, arguments, decision, and live row.

    ``decision`` is the queued addition and is ``None`` for a proposal the four-agent gate
    rejected (it never reached the queue). ``live_entry`` is present only once HR approved.
    """

    proposal: DictionaryProposal
    arguments: list[AgentRun]
    decision: PendingDictionaryAddition | None
    live_entry: Dictionary | None


def reconstruct_proposal_audit(session: Session, proposal_id: uuid.UUID) -> ProposalAudit:
    """Assemble the full provenance chain for one growth proposal.

    Args:
        session: An open database session; no writes are issued.
        proposal_id: The proposal rooting the chain — a dictionary entry's ``source_proposal_id``
            or a queued addition's ``proposal_id``.

    Returns:
        The proposal with its four agent arguments (in role order), the HR decision if the phrase
        advanced to the queue, and the live dictionary row if it was approved.

    Raises:
        ProposalNotFoundError: if no proposal has this id.
    """
    proposal = session.get(DictionaryProposal, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(proposal_id)

    runs = session.scalars(select(AgentRun).where(AgentRun.proposal_id == proposal_id)).all()
    arguments = sorted(runs, key=lambda run: _AGENT_ORDER.get(run.agent_name, len(_AGENT_ORDER)))

    decision = proposal.pending_addition

    live_entry = session.scalars(
        select(Dictionary).where(Dictionary.source_proposal_id == proposal_id)
    ).first()

    return ProposalAudit(
        proposal=proposal,
        arguments=list(arguments),
        decision=decision,
        live_entry=live_entry,
    )
