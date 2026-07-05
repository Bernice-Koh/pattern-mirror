"""add peer_feedback: an employee's peer feedback, the promotion drift reference

Persists the three-field peer feedback a Promotion Writeup drift check runs against (#119).
Rows are owned by the employee ``subjects`` row; the promotion writeup resolves them through
its ``subject_id``, so the drift stage reuses the feedback engine with a swapped reference
corpus (design spec §8).

Revision ID: 0015_add_peer_feedback
Revises: 0014_add_jd_criteria
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_add_peer_feedback"
down_revision: str | None = "0014_add_jd_criteria"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "peer_feedback",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("author_label", sa.String(), nullable=False),
        sa.Column("strengths", sa.Text(), nullable=False),
        sa.Column("development", sa.Text(), nullable=False),
        sa.Column("overall", sa.Text(), nullable=False),
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
            name=op.f("fk_peer_feedback_subject_id_subjects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_peer_feedback")),
    )
    op.create_index(
        "ix_peer_feedback_subject_id_position",
        "peer_feedback",
        ["subject_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("peer_feedback")
