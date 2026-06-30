"""add the calibration_runs table for persisted gold-set measurements

Stores each ``jobs.calibrate`` run — agreement, ECE, Brier, scored count, and the per-stage
precision/recall as JSONB — so the HR Portal can chart calibration over time (#23, #70, §11).
Gold-set measurement of the engine: no owner, no document content.

Revision ID: 0009_add_calibration_runs
Revises: 0008_add_flag_interactions
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_add_calibration_runs"
down_revision: str | None = "0008_add_flag_interactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calibration_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agreement", sa.Float(), nullable=True),
        sa.Column("ece", sa.Float(), nullable=True),
        sa.Column("brier", sa.Float(), nullable=True),
        sa.Column("scored_count", sa.Integer(), nullable=False),
        sa.Column("per_stage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calibration_runs")),
    )


def downgrade() -> None:
    op.drop_table("calibration_runs")
