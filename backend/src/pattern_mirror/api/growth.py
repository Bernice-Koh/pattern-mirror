"""HR-gated dictionary-growth approval endpoints (#90).

The backend the HR review-queue surface (#72) calls: list the additions awaiting a decision, then
approve, reject, or defer one. Approve creates a live dictionary row (the phrase becomes a
deterministic hit); reject and defer only record the decision. Thin handlers over
``services.dictionary_approval`` — the session dependency commits on success, and the router-level
``require_hr`` gate keeps the whole surface HR-only.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_principal, require_hr
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import BiasCategory, CitationSourceType, DictionaryAdditionStatus
from pattern_mirror.models.growth import PendingDictionaryAddition
from pattern_mirror.services.auth import SessionPrincipal
from pattern_mirror.services.dictionary_approval import (
    approve_addition,
    defer_addition,
    reject_addition,
)

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


def _serialise_addition(addition: PendingDictionaryAddition) -> PendingAdditionResponse:
    citation = addition.proposal.citation
    return PendingAdditionResponse(
        id=addition.id,
        phrase=addition.phrase,
        proposed_category=addition.proposed_category,
        explanation=addition.explanation,
        status=addition.status,
        created_at=addition.created_at,
        decided_at=addition.decided_at,
        citation=(
            CitationSummary(
                source_type=citation.source_type,
                title=citation.title,
                reference=citation.reference,
                publication_year=citation.publication_year,
                finding=citation.finding,
            )
            if citation is not None
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
