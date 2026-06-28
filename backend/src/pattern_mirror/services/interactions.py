"""Record a manager's response to a flag, and toggle suppression on a dismiss.

The write side of flag interactions (#62). Every accept/dismiss/undo is logged as an
append-only ``flag_interactions`` event — the raw signal behind the adoption metrics (§13).
A dismiss also writes (or reactivates) the ``flag_dismissals`` row whose signature the
suppression Module reads on the next run (#56); an undo deactivates it. The dismissal's
signature is copied straight off the persisted flag, so it cannot drift from the flag the
manager actually saw.
"""

import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import FlagNotFoundError
from pattern_mirror.models.engine import Flag, FlagDismissal, FlagInteraction
from pattern_mirror.models.enums import FlagInteractionKind

_log = structlog.get_logger("pattern_mirror.services.interactions")


@dataclass(frozen=True)
class InteractionResult:
    """The persisted interaction event and the dismissal it toggled, if any."""

    interaction: FlagInteraction
    dismissal: FlagDismissal | None


def _signature_match(flag: Flag) -> list[ColumnElement[bool]]:
    """The dismissal-signature filter for a flag (rule_id is None for contextual flags)."""
    rule_match = (
        FlagDismissal.rule_id.is_(None)
        if flag.dictionary_entry_id is None
        else FlagDismissal.rule_id == flag.dictionary_entry_id
    )
    return [
        FlagDismissal.document_id == flag.document_id,
        rule_match,
        FlagDismissal.normalised_span == flag.normalised_span,
        FlagDismissal.sentence_fingerprint == flag.sentence_fingerprint,
    ]


def _toggle_dismissal(session: Session, flag: Flag, *, active: bool) -> FlagDismissal | None:
    """Set the flag's dismissal active state, creating the row on a first dismiss.

    Reusing the existing row keeps one dismissal per signature, so repeated dismiss/undo
    cycles stay idempotent. An undo of a flag that was never dismissed is a no-op.
    """
    existing = session.scalars(select(FlagDismissal).where(*_signature_match(flag))).first()
    if existing is not None:
        existing.active = active
        return existing
    if not active:
        return None
    dismissal = FlagDismissal(
        document_id=flag.document_id,
        rule_id=flag.dictionary_entry_id,
        normalised_span=flag.normalised_span,
        sentence_fingerprint=flag.sentence_fingerprint,
        active=True,
    )
    session.add(dismissal)
    return dismissal


def record_interaction(
    session: Session,
    *,
    flag_id: uuid.UUID,
    owner_id: uuid.UUID,
    kind: FlagInteractionKind,
    accepted_alternative: str | None = None,
) -> InteractionResult:
    """Log an interaction event and apply its suppression side effect.

    Args:
        session: The active session (committed by the caller).
        flag_id: The flag the manager responded to.
        owner_id: The current manager; a flag on another owner's document is treated as absent.
        kind: accept, dismiss, or undo.
        accepted_alternative: The recommendation taken, on an accept.

    Returns:
        The persisted event and the dismissal it created or toggled, if any.

    Raises:
        FlagNotFoundError: if the flag is absent or owned by another user.
    """
    flag = session.get(Flag, flag_id)
    if flag is None or flag.document.owner_id != owner_id:
        raise FlagNotFoundError(flag_id)

    interaction = FlagInteraction(
        flag_id=flag.id, kind=kind, accepted_alternative=accepted_alternative
    )
    session.add(interaction)

    dismissal: FlagDismissal | None = None
    if kind is FlagInteractionKind.dismiss:
        dismissal = _toggle_dismissal(session, flag, active=True)
    elif kind is FlagInteractionKind.undo:
        dismissal = _toggle_dismissal(session, flag, active=False)

    session.flush()
    _log.info(
        "flag.interaction_recorded",
        flag_id=str(flag.id),
        document_id=str(flag.document_id),
        kind=kind,
        dismissal_id=str(dismissal.id) if dismissal else None,
    )
    return InteractionResult(interaction=interaction, dismissal=dismissal)
