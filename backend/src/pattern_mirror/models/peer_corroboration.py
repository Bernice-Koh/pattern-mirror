"""Peer corroboration: whether an employee's peers evidence each promotion-rubric criterion.

One row per (employee, rubric criterion) recording whether peer feedback supports that criterion
and the verbatim peer quote that does. This is the "what peers say" evidence the Promotion Writeup
surfaces against the rubric — mocked as synthetic data for the MVP, the same way peer feedback is
(design spec §8). It is a fact about the employee, not the writeup, so it is stored static and read
as surface context rather than recomputed per analysis run.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.identity import Subject


class PeerCorroboration(TimestampMixin, Base):
    """One rubric criterion and whether an employee's peers evidence it, with the peer quote."""

    __tablename__ = "peer_corroboration"
    __table_args__ = (Index("ix_peer_corroboration_subject_id_position", "subject_id", "position"),)

    id: Mapped[uuid_pk]
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    criterion: Mapped[str] = mapped_column(Text)
    corroborated: Mapped[bool] = mapped_column()
    evidence: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)

    subject: Mapped["Subject"] = relationship(back_populates="peer_corroboration")
