"""add jd_criteria: a JD's stated criteria, the feedback drift reference

Persists the criteria a Feedback Checkpoint drift check runs against (#116). Rows are owned by
the JD document; feedback resolves them through ``documents.reference_jd_id``, so one criteria
set is shared across every feedback note for that role.

Revision ID: 0014_add_jd_criteria
Revises: 0013_add_drift_findings
Create Date: 2026-07-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_add_jd_criteria"
down_revision: str | None = "0013_add_drift_findings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jd_criteria",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("jd_document_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["jd_document_id"],
            ["documents.id"],
            name=op.f("fk_jd_criteria_jd_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jd_criteria")),
    )
    op.create_index(
        "ix_jd_criteria_jd_document_id_position",
        "jd_criteria",
        ["jd_document_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("jd_criteria")
