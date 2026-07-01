"""Reconstruct a growth proposal's chain from what the loop persisted, without mutating it.

Covers the approved chain (arguments in role order, citation, HR decision, live row), both
rejected flavours (HR-rejected and gate-rejected), the read-only guarantee, and the not-found
case. Asserted against the test database.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import ProposalNotFoundError
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import (
    AgentName,
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.dictionary_approval import approve_addition, reject_addition
from pattern_mirror.services.growth_audit import reconstruct_proposal_audit

pytestmark = pytest.mark.db

# A synthetic phrase absent from the seeded SG lexicon, so approval creates a fresh row.
_PHRASE = "synergy ninja"
_LEMMA_KEY = "synergy ninja"


def _hr_user(db_session: Session) -> User:
    user = User(
        external_user_id=f"audit-hr-{uuid.uuid4()}",
        legal_name="Audit HR Reviewer",
        email=f"audit.hr.{uuid.uuid4()}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _record_agents(db_session: Session, proposal_id: uuid.UUID, *, with_citation: bool) -> None:
    """Log the four agents against a proposal, in a shuffled insert order to prove sorting."""
    outputs = {
        AgentName.categorizer: {"scope": "general", "reasoning": "Biased across hiring broadly."},
        AgentName.proposer: {
            "supports_inclusion": True,
            "category": BiasCategory.age.value,
            "reasoning": "Youth-coded; deters older applicants.",
        },
        AgentName.citation: {
            "found_support": with_citation,
            "citation": (
                {
                    "source_type": CitationSourceType.regulatory.value,
                    "title": "Fair hiring guideline",
                    "reference": "TAFEP-2021-3",
                    "publication_year": 2021,
                    "finding": "The phrasing discourages older applicants.",
                }
                if with_citation
                else None
            ),
            "reasoning": "Regulatory guidance supports the concern."
            if with_citation
            else "No credible source found.",
        },
        AgentName.skeptic: {
            "supports_inclusion": True,
            "reasoning": "Objection considered; still merits an entry.",
        },
    }
    for agent_name, output in outputs.items():
        db_session.add(
            AgentRun(
                agent_name=agent_name,
                model="claude-test",
                input={"phrase": _PHRASE},
                output=output,
                proposal_id=proposal_id,
            )
        )
    db_session.flush()


def _seed_reviewed(
    db_session: Session,
    *,
    lemma_key: str = _LEMMA_KEY,
    with_citation: bool = True,
    advanced: bool = True,
) -> DictionaryProposal:
    """A proposal with its four logged arguments, a citation, and (if advanced) a queue row."""
    citation_id = None
    if with_citation:
        citation = Citation(
            source_type=CitationSourceType.regulatory,
            title="Fair hiring guideline",
            reference="TAFEP-2021-3",
            publication_year=2021,
            finding="The phrasing discourages older applicants.",
        )
        db_session.add(citation)
        db_session.flush()
        citation_id = citation.id
    proposal = DictionaryProposal(phrase=_PHRASE, lemma_key=lemma_key, citation_id=citation_id)
    db_session.add(proposal)
    db_session.flush()
    _record_agents(db_session, proposal.id, with_citation=with_citation)
    if advanced:
        db_session.add(
            PendingDictionaryAddition(
                proposal_id=proposal.id,
                phrase=_PHRASE,
                lemma_key=lemma_key,
                proposed_category=BiasCategory.age,
                explanation="Youth-coded phrasing that deters older candidates.",
            )
        )
        db_session.flush()
    return proposal


def test_approved_chain_reconstructs_in_role_order(db_session: Session) -> None:
    actor = _hr_user(db_session)
    proposal = _seed_reviewed(db_session)
    addition = proposal.pending_addition
    assert addition is not None
    approve_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    audit = reconstruct_proposal_audit(db_session, proposal.id)

    assert [run.agent_name for run in audit.arguments] == [
        AgentName.proposer,
        AgentName.skeptic,
        AgentName.categorizer,
        AgentName.citation,
    ]
    assert audit.proposal.citation is not None
    assert audit.decision is not None
    assert audit.decision.status is DictionaryAdditionStatus.approved
    assert audit.decision.decided_by == actor.id
    assert audit.live_entry is not None
    assert audit.live_entry.term == _PHRASE


def test_hr_rejected_chain_reconstructs_without_a_live_row(db_session: Session) -> None:
    actor = _hr_user(db_session)
    proposal = _seed_reviewed(db_session)
    addition = proposal.pending_addition
    assert addition is not None
    reject_addition(db_session, addition_id=addition.id, actor_id=actor.id)

    audit = reconstruct_proposal_audit(db_session, proposal.id)

    assert len(audit.arguments) == 4
    assert audit.decision is not None
    assert audit.decision.status is DictionaryAdditionStatus.rejected
    assert audit.live_entry is None


def test_gate_rejected_proposal_reconstructs_its_arguments(db_session: Session) -> None:
    # The four-agent gate rejected it, so it never reached the queue: no decision, no live row,
    # but the proposal and its arguments remain fully reconstructable.
    proposal = _seed_reviewed(db_session, with_citation=False, advanced=False)

    audit = reconstruct_proposal_audit(db_session, proposal.id)

    assert len(audit.arguments) == 4
    assert audit.decision is None
    assert audit.live_entry is None
    assert audit.proposal.citation is None


def test_reconstruction_is_read_only(db_session: Session) -> None:
    proposal = _seed_reviewed(db_session)

    def _counts() -> tuple[int, int, int]:
        return (
            db_session.scalar(select(func.count()).select_from(AgentRun)) or 0,
            db_session.scalar(select(func.count()).select_from(Dictionary)) or 0,
            db_session.scalar(select(func.count()).select_from(PendingDictionaryAddition)) or 0,
        )

    before = _counts()
    reconstruct_proposal_audit(db_session, proposal.id)
    assert _counts() == before


def test_unknown_proposal_raises_not_found(db_session: Session) -> None:
    with pytest.raises(ProposalNotFoundError):
        reconstruct_proposal_audit(db_session, uuid.uuid4())
