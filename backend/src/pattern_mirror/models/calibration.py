"""Persisted gold-set calibration measurements: ``calibration_runs`` (#23, #70).

Each row is one run of ``jobs.calibrate`` against the gold set — agreement, ECE, Brier, and the
per-stage precision/recall — anchored by ``created_at`` so the HR Portal can chart calibration
over time (§11). Gold-set measurement of the engine, not per-manager data: no owner, no document
text, nothing that could identify an individual. Per-stage metrics are kept as JSONB (the
``report_fields`` shape) since they are read whole for display, never queried by stage.
"""

from typing import Any

from sqlalchemy import Float, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from pattern_mirror.db.base import Base
from pattern_mirror.models.columns import uuid_pk
from pattern_mirror.models.mixins import CreatedAtMixin


class CalibrationRun(CreatedAtMixin, Base):
    """One gold-set calibration measurement of the engine, the time-series point for #71."""

    __tablename__ = "calibration_runs"

    id: Mapped[uuid_pk]
    agreement: Mapped[float | None] = mapped_column(Float)
    ece: Mapped[float | None] = mapped_column(Float)
    brier: Mapped[float | None] = mapped_column(Float)
    scored_count: Mapped[int] = mapped_column(Integer)
    per_stage: Mapped[dict[str, Any]] = mapped_column(JSONB)
