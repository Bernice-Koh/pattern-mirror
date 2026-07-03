"""Peer feedback: the reference a promotion writeup's drift check is measured against.

One row per peer submission about an employee, owned by the ``subjects`` row (design spec §8).
UBS collects this as three free-text fields — strengths, development, overall — mocked as
synthetic data for the MVP. Promotion resolves an employee's rows into a single reference text,
so the drift stage checks a writeup against peer feedback exactly as feedback checks against JD
criteria: the same engine, a swapped reference corpus.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from pattern_mirror.models.identity import Subject


class PeerFeedback(TimestampMixin, Base):
    """One peer's three-field feedback about an employee, a promotion drift reference unit."""

    __tablename__ = "peer_feedback"
    __table_args__ = (Index("ix_peer_feedback_subject_id_position", "subject_id", "position"),)

    id: Mapped[uuid_pk]
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    author_label: Mapped[str] = mapped_column(String)
    strengths: Mapped[str] = mapped_column(Text)
    development: Mapped[str] = mapped_column(Text)
    overall: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)

    subject: Mapped["Subject"] = relationship(back_populates="peer_feedback")
