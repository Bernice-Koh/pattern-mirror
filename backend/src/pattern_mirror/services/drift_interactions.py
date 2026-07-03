"""Record a manager's dismiss/undo on a drift finding, and toggle its suppression.

The write side of drift-finding interactions (#65), mirroring flag interactions. Every dismiss/undo
is logged as an append-only ``drift_interactions`` event; a dismiss also writes (or reactivates)
the ``drift_dismissals`` row whose signature suppresses the criterion on the next run, and an undo
deactivates it. The signature is copied straight off the finding, so it cannot drift from what the
manager saw.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DriftFindingNotFoundError
from pattern_mirror.models.drift import (
    DriftFinding,
    DriftFindingDismissal,
    DriftFindingInteraction,
)
from pattern_mirror.models.enums import DriftFindingInteractionKind

_log = structlog.get_logger("pattern_mirror.services.drift_interactions")


@dataclass(frozen=True)
class DriftInteractionResult:
    """The persisted interaction event and the dismissal it toggled, if any."""

    interaction: DriftFindingInteraction
    dismissal: DriftFindingDismissal | None


def _toggle_dismissal(
    session: Session, finding: DriftFinding, *, active: bool
) -> DriftFindingDismissal | None:
    """Set the finding's dismissal active state, creating the row on a first dismiss.

    Reusing the existing row keeps one dismissal per signature, so repeated dismiss/undo cycles
    stay idempotent. An undo of a finding that was never dismissed is a no-op.
    """
    existing = session.scalars(
        select(DriftFindingDismissal).where(
            DriftFindingDismissal.document_id == finding.document_id,
            DriftFindingDismissal.reference_kind == finding.reference_kind,
            DriftFindingDismissal.normalised_criterion == finding.normalised_criterion,
        )
    ).first()
    if existing is not None:
        existing.active = active
        return existing
    if not active:
        return None
    dismissal = DriftFindingDismissal(
        document_id=finding.document_id,
        reference_kind=finding.reference_kind,
        normalised_criterion=finding.normalised_criterion,
        active=True,
    )
    session.add(dismissal)
    return dismissal


def record_drift_interaction(
    session: Session,
    *,
    finding_id: uuid.UUID,
    owner_id: uuid.UUID,
    kind: DriftFindingInteractionKind,
) -> DriftInteractionResult:
    """Log a dismiss/undo on a drift finding and apply its suppression side effect.

    Args:
        session: The active session (committed by the caller).
        finding_id: The drift finding the manager responded to.
        owner_id: The current manager; a finding on another owner's document is treated as absent.
        kind: dismiss or undo.

    Returns:
        The persisted event and the dismissal it created or toggled, if any.

    Raises:
        DriftFindingNotFoundError: if the finding is absent or owned by another user.
    """
    finding = session.get(DriftFinding, finding_id)
    if finding is None or finding.document.owner_id != owner_id:
        raise DriftFindingNotFoundError(finding_id)

    interaction = DriftFindingInteraction(drift_finding_id=finding.id, kind=kind)
    session.add(interaction)

    dismissal: DriftFindingDismissal | None = None
    if kind is DriftFindingInteractionKind.dismiss:
        dismissal = _toggle_dismissal(session, finding, active=True)
    elif kind is DriftFindingInteractionKind.undo:
        dismissal = _toggle_dismissal(session, finding, active=False)

    session.flush()
    _log.info(
        "drift.interaction_recorded",
        drift_finding_id=str(finding.id),
        document_id=str(finding.document_id),
        kind=kind,
        dismissal_id=str(dismissal.id) if dismissal else None,
    )
    return DriftInteractionResult(interaction=interaction, dismissal=dismissal)
