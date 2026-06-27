"""add the flags.recommendations column for Stage-5 rewrites

The Recommendations Agent (#50) attaches 2-3 evidence-anchored alternative phrasings to
each above-threshold contextual flag. They are stored as JSONB on the flag they belong to —
read with the flag, never queried by their structure — rather than a separate table.
Nullable: a flag the Agent never runs on (dictionary, below threshold, dismissed) has none.

Revision ID: 0007_add_flag_recommendations
Revises: 0006_drop_judge_hallucination
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_add_flag_recommendations"
down_revision: str | None = "0006_drop_judge_hallucination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("flags", sa.Column("recommendations", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("flags", "recommendations")
