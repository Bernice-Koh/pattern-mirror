"""remove the unused judge hallucination_risk score

ADR-0007 makes the Adjudicator the single deterministic gate for span existence, so the Judge
emits confidence only; the hallucination-risk score is removed from the Judge schema and from
persistence. This drops the ``flags.judge_hallucination_risk`` column added in 0001. Downgrade
recreates it nullable; prior values are not restored.

Revision ID: 0006_drop_judge_hallucination
Revises: 0005_remove_severity
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_drop_judge_hallucination"
down_revision: str | None = "0005_remove_severity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("flags", "judge_hallucination_risk")


def downgrade() -> None:
    op.add_column("flags", sa.Column("judge_hallucination_risk", sa.Numeric(4, 3), nullable=True))
