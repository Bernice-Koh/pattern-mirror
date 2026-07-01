"""Resolve queued dictionary-growth additions: HR approve, reject, or defer (#90).

Approve materialises a live ``dictionaries`` row from the queued addition — so the phrase
becomes a deterministic Stage-1 hit on the next run (design spec §3) — and stamps the decision.
Reject and defer add no row; they only stamp the decision. Every path records who decided and
when, the audit #91 reads. The caller owns the transaction: these flush but do not commit.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import (
    AdditionAlreadyDecidedError,
    DictionaryEntryExistsError,
    PendingAdditionNotFoundError,
)
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import DictionaryAdditionStatus
from pattern_mirror.models.growth import PendingDictionaryAddition

_log = structlog.get_logger("pattern_mirror.services.dictionary_approval")

# The MVP lexicon is Singapore-only, matching the analysis path (services.analysis).
_REGION_CODE = "SG"

# A queue item is still decidable from these states; approved and rejected are terminal.
_DECIDABLE = frozenset({DictionaryAdditionStatus.pending, DictionaryAdditionStatus.deferred})


def _load_decidable(session: Session, addition_id: uuid.UUID) -> PendingDictionaryAddition:
    """Load an addition that is still open to a decision, or raise.

    Raises:
        PendingAdditionNotFoundError: if no addition has this id.
        AdditionAlreadyDecidedError: if it was already approved or rejected.
    """
    addition = session.get(PendingDictionaryAddition, addition_id)
    if addition is None:
        raise PendingAdditionNotFoundError(addition_id)
    if addition.status not in _DECIDABLE:
        raise AdditionAlreadyDecidedError(addition_id, addition.status.value)
    return addition


def _stamp(
    addition: PendingDictionaryAddition,
    *,
    actor_id: uuid.UUID,
    status: DictionaryAdditionStatus,
) -> None:
    addition.status = status
    addition.decided_by = actor_id
    addition.decided_at = datetime.now(UTC)


def approve_addition(
    session: Session, *, addition_id: uuid.UUID, actor_id: uuid.UUID
) -> Dictionary:
    """Approve an addition: create its live dictionary row and stamp the decision.

    Args:
        session: The active session (committed by the caller).
        addition_id: The queued addition to approve.
        actor_id: The HR user making the decision, recorded as the entry's author.

    Returns:
        The newly created, active ``Dictionary`` entry.

    Raises:
        PendingAdditionNotFoundError: if the addition does not exist.
        AdditionAlreadyDecidedError: if it was already approved or rejected.
        DictionaryEntryExistsError: if an entry for this region, phrase, and category exists,
            which the ``(region_code, lemma_key, category)`` unique constraint would reject.
    """
    addition = _load_decidable(session, addition_id)
    proposal = addition.proposal
    # The advancement gate requires a citation, so an approvable addition always has one.
    assert proposal.citation_id is not None

    clash = session.scalars(
        select(Dictionary.id).where(
            Dictionary.region_code == _REGION_CODE,
            Dictionary.lemma_key == addition.lemma_key,
            Dictionary.category == addition.proposed_category,
        )
    ).first()
    if clash is not None:
        raise DictionaryEntryExistsError(addition.lemma_key, addition.proposed_category.value)

    entry = Dictionary(
        region_code=_REGION_CODE,
        category=addition.proposed_category,
        term=addition.phrase,
        lemma_key=addition.lemma_key,
        citation_id=proposal.citation_id,
        explanation=addition.explanation,
        last_updated_by=actor_id,
        source_proposal_id=proposal.id,
    )
    session.add(entry)
    _stamp(addition, actor_id=actor_id, status=DictionaryAdditionStatus.approved)
    session.flush()
    _log.info(
        "growth.addition_approved",
        addition_id=str(addition.id),
        dictionary_id=str(entry.id),
        lemma_key=addition.lemma_key,
        category=addition.proposed_category.value,
    )
    return entry


def reject_addition(
    session: Session, *, addition_id: uuid.UUID, actor_id: uuid.UUID
) -> PendingDictionaryAddition:
    """Reject an addition: stamp the decision and add no dictionary row.

    Raises:
        PendingAdditionNotFoundError: if the addition does not exist.
        AdditionAlreadyDecidedError: if it was already approved or rejected.
    """
    addition = _load_decidable(session, addition_id)
    _stamp(addition, actor_id=actor_id, status=DictionaryAdditionStatus.rejected)
    session.flush()
    _log.info("growth.addition_rejected", addition_id=str(addition.id))
    return addition


def defer_addition(
    session: Session, *, addition_id: uuid.UUID, actor_id: uuid.UUID
) -> PendingDictionaryAddition:
    """Defer an addition to a later review: stamp the decision, add no row, keep it decidable.

    Raises:
        PendingAdditionNotFoundError: if the addition does not exist.
        AdditionAlreadyDecidedError: if it was already approved or rejected.
    """
    addition = _load_decidable(session, addition_id)
    _stamp(addition, actor_id=actor_id, status=DictionaryAdditionStatus.deferred)
    session.flush()
    _log.info("growth.addition_deferred", addition_id=str(addition.id))
    return addition
