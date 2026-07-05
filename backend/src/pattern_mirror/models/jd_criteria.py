"""JD criteria: the reference a feedback note's drift check is measured against.

One row per stated criterion, owned by the JD document (design spec §2 View 2). Feedback
resolves its criteria through the JD it references (``documents.reference_jd_id``), so every
feedback note for a role shares one criteria set instead of carrying its own copy that could
drift apart. The criteria source is pluggable — seeded or manually entered now, AI-drafted
with a manager-confirm gate later (#122) — on this same table.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.documents import Document


class JdCriterion(TimestampMixin, Base):
    """One stated criterion of a JD, the unit a feedback drift check is measured against."""

    __tablename__ = "jd_criteria"
    __table_args__ = (
        Index("ix_jd_criteria_jd_document_id_position", "jd_document_id", "position"),
    )

    id: Mapped[uuid_pk]
    jd_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"))
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)

    jd_document: Mapped["Document"] = relationship(back_populates="jd_criteria")
