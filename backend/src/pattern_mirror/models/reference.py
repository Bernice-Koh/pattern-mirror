"""Reference data: jurisdiction ``regions`` and source ``citations``.

``regions`` is a lookup table (D9) so adding a market is an INSERT, not a
migration. ``citations`` is its own entity (D4) because one source is referenced
by many dictionary entries and flags; inlining it would duplicate and risk
update anomalies, weakening the "every flag cites a verifiable source" promise.
"""

from typing import TYPE_CHECKING

from sqlalchemy import SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.enums import CitationSourceType, citation_source_type_enum
from pattern_mirror.models.mixins import CreatedAtMixin, TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.dictionary import Dictionary
    from pattern_mirror.models.engine import Flag


class Region(CreatedAtMixin, Base):
    """A jurisdiction whose fair-employment lexicon is scoped to it (e.g. ``SG``)."""

    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(server_default=text("true"))

    dictionaries: Mapped[list["Dictionary"]] = relationship(back_populates="region")


class Citation(TimestampMixin, Base):
    """A verifiable source (TAFEP guideline, study, regulation) cited by rules and flags."""

    __tablename__ = "citations"

    id: Mapped[uuid_pk]
    source_type: Mapped[CitationSourceType] = mapped_column(citation_source_type_enum)
    title: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(SmallInteger)
    finding: Mapped[str | None] = mapped_column(Text)

    dictionaries: Mapped[list["Dictionary"]] = relationship(back_populates="citation")
    flags: Mapped[list["Flag"]] = relationship(back_populates="citation")
