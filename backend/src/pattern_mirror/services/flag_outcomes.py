"""Group a document's persisted flags into the distinct things the manager actually saw.

Shared by the manager-scoped Pattern Aggregator (#66) and the firm-wide HR aggregates (#70):
both reduce raw flag rows to one record per ``(span, fingerprint)`` and drop groups that never
surfaced. Pure reads — no owner scoping happens here; the caller decides which documents to pass.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import BiasCategory, FlagInteractionKind


@dataclass(frozen=True)
class FlagGroup:
    """One distinct flagged thing the manager saw: a ``(document, span, fingerprint)`` group."""

    document_id: uuid.UUID
    category: BiasCategory
    raw_span: str
    interaction_kinds: tuple[FlagInteractionKind, ...]


def surfaced_flag_groups(session: Session, document_ids: list[uuid.UUID]) -> list[FlagGroup]:
    """Group each document's flags by ``(span, fingerprint)`` and keep the ones the manager saw.

    Flags regenerate every run, so a dismissal recorded on one run's flag and the surviving flag
    on a later run share a signature; grouping collects the decision wherever it was logged. A group
    never surfaced (all suppressed, no interaction) is a flag the manager never saw.
    """
    flags = session.scalars(
        select(Flag)
        .where(Flag.document_id.in_(document_ids))
        .options(selectinload(Flag.interactions))
    ).all()
    by_signature: dict[tuple[uuid.UUID, str, str], list[Flag]] = defaultdict(list)
    for flag in flags:
        signature = (flag.document_id, flag.normalised_span, flag.sentence_fingerprint)
        by_signature[signature].append(flag)

    groups: list[FlagGroup] = []
    for (document_id, _, _), group in by_signature.items():
        interactions = sorted(
            (event for flag in group for event in flag.interactions),
            key=lambda event: event.created_at,
        )
        surfaced = any(not flag.suppressed for flag in group) or bool(interactions)
        if not surfaced:
            continue
        groups.append(
            FlagGroup(
                document_id=document_id,
                category=group[0].category,
                raw_span=group[0].raw_span,
                interaction_kinds=tuple(event.kind for event in interactions),
            )
        )
    return groups
