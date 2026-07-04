"""Promotion rubric: the criteria a promotion writeup's drift check is measured against.

One row per stated criterion, keyed by the target level (``level_label``) rather than a document,
so every promotion to a level shares one rubric — the promotion analogue of ``jd_criteria`` for a
role (design spec §8). A writeup resolves its rubric through its ``role_title``, so the drift stage
reuses the feedback engine with a swapped reference corpus: the rubric in place of JD criteria.
"""

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.mixins import TimestampMixin


class PromotionRubricCriterion(TimestampMixin, Base):
    """One stated criterion of a level's promotion rubric, a promotion drift reference unit."""

    __tablename__ = "promotion_rubric_criteria"
    __table_args__ = (
        Index("ix_promotion_rubric_criteria_level_label_position", "level_label", "position"),
    )

    id: Mapped[uuid_pk]
    level_label: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
