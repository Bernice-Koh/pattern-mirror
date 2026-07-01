"""HR-gated dictionary-growth approval endpoints (#90).

The backend the HR review-queue surface (#72) calls: list the additions awaiting a decision, then
approve, reject, or defer one. Approve creates a live dictionary row (the phrase becomes a
deterministic hit); reject and defer only record the decision. Thin handlers over
``services.dictionary_approval`` — the session dependency commits on success, and the router-level
``require_hr`` gate keeps the whole surface HR-only.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_principal, require_hr
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import (
    AgentName,
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
)
from pattern_mirror.models.growth import PendingDictionaryAddition
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.auth import SessionPrincipal
from pattern_mirror.services.dictionary_approval import (
    approve_addition,
    defer_addition,
    reject_addition,
)
from pattern_mirror.services.growth_audit import ProposalAudit, reconstruct_proposal_audit

router = APIRouter(prefix="/growth", tags=["growth"], dependencies=[Depends(require_hr)])

# The queue shows every addition still open to a decision; approved/rejected ones have left it.
_OPEN_STATUSES = (DictionaryAdditionStatus.pending, DictionaryAdditionStatus.deferred)


class CitationSummary(BaseModel):
    """The source backing a proposed addition, shown so HR reviews a case, not a bare phrase."""

    source_type: CitationSourceType
    title: str
    reference: str
    publication_year: int | None
    finding: str | None


class PendingAdditionResponse(BaseModel):
    """One queued addition awaiting an HR decision."""

    id: uuid.UUID
    proposal_id: uuid.UUID
    phrase: str
    proposed_category: BiasCategory
    explanation: str
    status: DictionaryAdditionStatus
    created_at: datetime
    decided_at: datetime | None
    citation: CitationSummary | None


class DictionaryEntryResponse(BaseModel):
    """The live dictionary row an approval created."""

    id: uuid.UUID
    region_code: str
    category: BiasCategory
    term: str
    lemma_key: str
    citation_id: uuid.UUID


class AgentArgumentResponse(BaseModel):
    """One growth agent's logged argument, as the audit replays it."""

    agent_name: AgentName
    model: str
    output: dict[str, Any]


class DecisionResponse(BaseModel):
    """The HR decision on an addition that reached the queue."""

    status: DictionaryAdditionStatus
    decided_by: uuid.UUID | None
    decided_at: datetime | None


class LiveEntryResponse(BaseModel):
    """The live dictionary row an approval produced, if the chain got that far."""

    id: uuid.UUID
    term: str
    active: bool


class ProposalAuditResponse(BaseModel):
    """A growth proposal's full provenance chain: arguments, citation, decision, live row."""

    proposal_id: uuid.UUID
    phrase: str
    lemma_key: str
    proposed_at: datetime
    advanced: bool
    arguments: list[AgentArgumentResponse]
    citation: CitationSummary | None
    decision: DecisionResponse | None
    live_entry: LiveEntryResponse | None


def _serialise_addition(addition: PendingDictionaryAddition) -> PendingAdditionResponse:
    return PendingAdditionResponse(
        id=addition.id,
        proposal_id=addition.proposal_id,
        phrase=addition.phrase,
        proposed_category=addition.proposed_category,
        explanation=addition.explanation,
        status=addition.status,
        created_at=addition.created_at,
        decided_at=addition.decided_at,
        citation=_serialise_citation(addition.proposal.citation),
    )


def _serialise_citation(citation: Citation | None) -> CitationSummary | None:
    if citation is None:
        return None
    return CitationSummary(
        source_type=citation.source_type,
        title=citation.title,
        reference=citation.reference,
        publication_year=citation.publication_year,
        finding=citation.finding,
    )


def _serialise_audit(audit: ProposalAudit) -> ProposalAuditResponse:
    proposal = audit.proposal
    decision = audit.decision
    entry = audit.live_entry
    return ProposalAuditResponse(
        proposal_id=proposal.id,
        phrase=proposal.phrase,
        lemma_key=proposal.lemma_key,
        proposed_at=proposal.created_at,
        advanced=decision is not None,
        arguments=[
            AgentArgumentResponse(agent_name=run.agent_name, model=run.model, output=run.output)
            for run in audit.arguments
        ],
        citation=_serialise_citation(proposal.citation),
        decision=(
            DecisionResponse(
                status=decision.status,
                decided_by=decision.decided_by,
                decided_at=decision.decided_at,
            )
            if decision is not None
            else None
        ),
        live_entry=(
            LiveEntryResponse(id=entry.id, term=entry.term, active=entry.active)
            if entry is not None
            else None
        ),
    )


@router.get("/pending-additions", summary="List dictionary additions awaiting HR decision (HR)")
def list_pending_additions(
    session: Annotated[Session, Depends(get_session)],
) -> list[PendingAdditionResponse]:
    """Return the growth additions still open to a decision, oldest first."""
    additions = session.scalars(
        select(PendingDictionaryAddition)
        .where(PendingDictionaryAddition.status.in_(_OPEN_STATUSES))
        .order_by(PendingDictionaryAddition.created_at)
    ).all()
    return [_serialise_addition(addition) for addition in additions]


@router.post(
    "/pending-additions/{addition_id}/approve",
    summary="Approve an addition into a live dictionary row (HR)",
)
def approve(
    addition_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[SessionPrincipal, Depends(get_current_principal)],
) -> DictionaryEntryResponse:
    """Create the live dictionary entry and record the approval."""
    entry = approve_addition(session, addition_id=addition_id, actor_id=principal.user_id)
    return DictionaryEntryResponse(
        id=entry.id,
        region_code=entry.region_code,
        category=entry.category,
        term=entry.term,
        lemma_key=entry.lemma_key,
        citation_id=entry.citation_id,
    )


@router.post(
    "/pending-additions/{addition_id}/reject",
    summary="Reject an addition without adding a dictionary row (HR)",
)
def reject(
    addition_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[SessionPrincipal, Depends(get_current_principal)],
) -> PendingAdditionResponse:
    """Record the rejection; no dictionary row is created."""
    addition = reject_addition(session, addition_id=addition_id, actor_id=principal.user_id)
    return _serialise_addition(addition)


@router.post(
    "/pending-additions/{addition_id}/defer",
    summary="Defer an addition to a later review (HR)",
)
def defer(
    addition_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    principal: Annotated[SessionPrincipal, Depends(get_current_principal)],
) -> PendingAdditionResponse:
    """Record the deferral; the addition stays open to a later decision."""
    addition = defer_addition(session, addition_id=addition_id, actor_id=principal.user_id)
    return _serialise_addition(addition)


@router.get(
    "/proposals/{proposal_id}/audit",
    summary="Reconstruct a growth proposal's full provenance chain (HR)",
)
def proposal_audit(
    proposal_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ProposalAuditResponse:
    """Return the trigger, four agent arguments, citation, decision, and live row for a proposal."""
    audit = reconstruct_proposal_audit(session, proposal_id)
    return _serialise_audit(audit)
