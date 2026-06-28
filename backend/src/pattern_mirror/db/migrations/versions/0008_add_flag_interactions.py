"""add the flag_interactions table for manager accept/dismiss/undo events

Records the manager's response to a surfaced flag (#62), the raw signal behind the
adoption metrics (design spec §13). Append-only; "ignored" is the absence of a row.
The dismiss/undo side effects on ``flag_dismissals`` reuse the existing table.

Revision ID: 0008_add_flag_interactions
Revises: 0007_add_flag_recommendations
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_add_flag_interactions"
down_revision: str | None = "0007_add_flag_recommendations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

flag_interaction_kind = postgresql.ENUM(
    "accept", "dismiss", "undo", name="flag_interaction_kind", create_type=False
)


def upgrade() -> None:
    flag_interaction_kind.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "flag_interactions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("flag_id", sa.Uuid(), nullable=False),
        sa.Column("kind", flag_interaction_kind, nullable=False),
        sa.Column("accepted_alternative", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flag_id"], ["flags.id"], name=op.f("fk_flag_interactions_flag_id_flags")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flag_interactions")),
    )
    op.create_index("ix_flag_interactions_flag_id", "flag_interactions", ["flag_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_flag_interactions_flag_id", table_name="flag_interactions")
    op.drop_table("flag_interactions")
    flag_interaction_kind.drop(op.get_bind(), checkfirst=True)
