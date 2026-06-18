"""The curated ``dictionaries`` lexicon behind Stage-1 deterministic flags.

Region-scoped (the orchestrator selects ``WHERE region_code = :region AND active``)
and every live entry carries a citation, enforcing the "every flag cites a
verifiable source" value prop. ``origin_candidate_id`` (provenance for grown
entries) is intentionally absent here: it arrives in migration 0005 with the
``dictionary_candidates`` table it references.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import (
    BiasCategory,
    Severity,
    bias_category_enum,
    severity_enum,
)
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.engine import Flag, FlagDismissal
    from pattern_mirror.models.reference import Citation, Region


class Dictionary(TimestampMixin, Base):
    """A curated biased term, scoped to a jurisdiction and backed by a citation."""

    __tablename__ = "dictionaries"
    __table_args__ = (
        UniqueConstraint(
            "region_code",
            "lemma_key",
            "category",
            name="uq_dictionaries_region_code_lemma_key_category",
        ),
        Index("ix_dictionaries_region_code_active", "region_code", "active"),
    )

    id: Mapped[uuid_pk]
    region_code: Mapped[str] = mapped_column(String(8), ForeignKey("regions.code"))
    category: Mapped[BiasCategory] = mapped_column(bias_category_enum)
    term: Mapped[str] = mapped_column(String)
    lemma_key: Mapped[str] = mapped_column(String)
    severity: Mapped[Severity] = mapped_column(severity_enum)
    citation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("citations.id"))
    explanation: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(server_default=text("true"))

    region: Mapped["Region"] = relationship(back_populates="dictionaries")
    citation: Mapped["Citation"] = relationship(back_populates="dictionaries")
    flags: Mapped[list["Flag"]] = relationship(back_populates="dictionary_entry")
    dismissals: Mapped[list["FlagDismissal"]] = relationship(back_populates="rule")
