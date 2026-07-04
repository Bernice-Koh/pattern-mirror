"""add promotion rubric + peer corroboration, the promotion writeup drift reference and evidence

Persists the criteria a Promotion Writeup drift check runs against — a rubric keyed by target
level, the promotion analogue of ``jd_criteria`` (#121) — and the per-employee
``peer_corroboration`` recording whether peers evidence each criterion. The rubric is the live
drift reference; the corroboration is static "what peers say" surface context, mocked for the MVP
like peer feedback (§8).

Revision ID: 0016_add_promotion_rubric
Revises: 0015_add_peer_feedback
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_add_promotion_rubric"
down_revision: str | None = "0015_add_peer_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "promotion_rubric_criteria",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("level_label", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_promotion_rubric_criteria")),
    )
    op.create_index(
        "ix_promotion_rubric_criteria_level_label_position",
        "promotion_rubric_criteria",
        ["level_label", "position"],
        unique=False,
    )

    op.create_table(
        "peer_corroboration",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("criterion", sa.Text(), nullable=False),
        sa.Column("corroborated", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_peer_corroboration_subject_id_subjects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_peer_corroboration")),
    )
    op.create_index(
        "ix_peer_corroboration_subject_id_position",
        "peer_corroboration",
        ["subject_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("peer_corroboration")
    op.drop_table("promotion_rubric_criteria")
