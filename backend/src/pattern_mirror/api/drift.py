"""Drift-finding endpoints: read a document's findings and record a dismiss/undo.

The one read contract the Feedback Checkpoint and Promotion Writeup surfaces render by (#65):
addressed vs unaddressed criteria with their evidence, in a single corpus-agnostic shape. The
surface maps ``reference_kind`` to its own label ("criteria" vs "peer feedback"). Thin over the
services — ownership is enforced there, and no ORM object crosses the boundary.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.models.drift import DriftFinding
from pattern_mirror.models.enums import DriftFindingInteractionKind, ReferenceKind
from pattern_mirror.models.identity import User
from pattern_mirror.services.drift_findings import list_drift_findings
from pattern_mirror.services.drift_interactions import record_drift_interaction

router = APIRouter(tags=["drift"])


class DriftFindingResponse(BaseModel):
    """One reference criterion and whether the document addresses it, with its evidence.

    ``reference_kind`` names the corpus (JD criteria or peer feedback) so both surfaces render the
    same shape. ``evidence`` and its offsets are present only on an addressed criterion.
    """

    id: uuid.UUID
    reference_kind: ReferenceKind
    criterion: str
    addressed: bool
    evidence: str | None
    evidence_start: int | None
    evidence_end: int | None


def _serialise_drift_finding(finding: DriftFinding) -> DriftFindingResponse:
    """Map a persisted drift finding into its response model (no ORM leaks out)."""
    return DriftFindingResponse(
        id=finding.id,
        reference_kind=finding.reference_kind,
        criterion=finding.criterion,
        addressed=finding.addressed,
        evidence=finding.evidence,
        evidence_start=finding.evidence_start,
        evidence_end=finding.evidence_end,
    )


class DriftInteractionRequest(BaseModel):
    """A manager's response to a drift finding."""

    kind: DriftFindingInteractionKind


class DriftInteractionResponse(BaseModel):
    """The persisted interaction event and whether it left an active dismissal."""

    id: uuid.UUID
    finding_id: uuid.UUID
    kind: DriftFindingInteractionKind
    dismissed: bool


@router.get(
    "/documents/{doc_id}/drift-findings",
    summary="List a document's latest-run drift findings",
)
def list_document_drift_findings(
    doc_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[DriftFindingResponse]:
    """Return the owner's latest-run, un-suppressed drift findings for the document."""
    findings = list_drift_findings(session, document_id=doc_id, owner_id=current_user.id)
    return [_serialise_drift_finding(finding) for finding in findings]


@router.post(
    "/drift-findings/{finding_id}/interactions",
    summary="Record a manager's dismiss/undo on a drift finding",
)
def create_drift_interaction(
    finding_id: uuid.UUID,
    request: DriftInteractionRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DriftInteractionResponse:
    """Persist the interaction and apply its suppression side effect."""
    result = record_drift_interaction(
        session,
        finding_id=finding_id,
        owner_id=current_user.id,
        kind=request.kind,
    )
    return DriftInteractionResponse(
        id=result.interaction.id,
        finding_id=finding_id,
        kind=request.kind,
        dismissed=result.dismissal is not None and result.dismissal.active,
    )
