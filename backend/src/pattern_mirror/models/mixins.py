"""Reusable timestamp columns mixed into the ORM models.

``created_at`` is on every table; ``updated_at`` only on mutable ones, touched by
the ORM ``onupdate`` hook (the design's "touch on update via app/ORM" rule —
no database trigger). Tables whose time columns carry domain meaning
(``user_roles.granted_at``, ``analysis_runs.started_at``) define their own
instead of using these.
"""

from datetime import datetime

from sqlalchemy import TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column


class CreatedAtMixin:
    """A single ``created_at TIMESTAMPTZ NOT NULL DEFAULT now()`` column."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """``created_at`` plus an ``updated_at`` touched on every ORM update."""

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
