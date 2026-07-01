"""Persistence for the dictionary-growth loop: proposals and the HR queue.

A ``dictionary_proposals`` row is written for every phrase the four-agent flow
evaluates (the arguments are logged even when it fails to advance); each agent's
reasoning attaches via ``agent_runs.proposal_id``. When 3-of-4 agree, a
``pending_dictionary_additions`` row queues the phrase for monthly HR approval.
"Did it advance?" needs no flag here — a queue row exists iff it did.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    BiasCategory,
    DictionaryAdditionStatus,
    bias_category_enum,
    dictionary_addition_status_enum,
)
from pattern_mirror.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from pattern_mirror.models.reference import Citation


class DictionaryProposal(CreatedAtMixin, Base):
    """A phrase evaluated by the four-agent flow, with its found citation."""

    __tablename__ = "dictionary_proposals"

    id: Mapped[uuid_pk]
    phrase: Mapped[str] = mapped_column(Text)
    lemma_key: Mapped[str] = mapped_column(String)
    citation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("citations.id"))

    citation: Mapped["Citation | None"] = relationship()
    pending_addition: Mapped["PendingDictionaryAddition | None"] = relationship(
        back_populates="proposal"
    )


class PendingDictionaryAddition(CreatedAtMixin, Base):
    """A proposal that cleared the 3-of-4 gate, awaiting bulk HR approval.

    ``proposed_category`` and ``explanation`` stage the eventual ``dictionaries`` row: the
    category the four agents settled on and the rationale a manager will read on the flag.
    ``decided_by`` / ``decided_at`` record who resolved the queue item and when — the audit
    #91 reads for reject/defer, which create no dictionary row of their own.
    """

    __tablename__ = "pending_dictionary_additions"

    id: Mapped[uuid_pk]
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dictionary_proposals.id"))
    phrase: Mapped[str] = mapped_column(Text)
    lemma_key: Mapped[str] = mapped_column(String)
    proposed_category: Mapped[BiasCategory] = mapped_column(bias_category_enum)
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[DictionaryAdditionStatus] = mapped_column(
        dictionary_addition_status_enum,
        server_default=DictionaryAdditionStatus.pending.value,
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    proposal: Mapped["DictionaryProposal"] = relationship(back_populates="pending_addition")
