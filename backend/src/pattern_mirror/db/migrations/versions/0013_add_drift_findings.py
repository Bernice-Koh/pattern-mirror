"""add drift-finding persistence: findings, signature dismissals, interaction log

Persists the drift agent's output (#65): ``drift_findings`` stores one reference criterion per
row (addressed/unaddressed, with a verbatim evidence span), ``drift_dismissals`` suppresses a
dismissed criterion on future runs by its ``(document_id, reference_kind, normalised_criterion)``
signature, and ``drift_interactions`` is the append-only dismiss/undo log. Mirrors the flag model.

Revision ID: 0013_add_drift_findings
Revises: 0012_add_drift_agent_name
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_add_drift_findings"
down_revision: str | None = "0012_add_drift_agent_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

reference_kind = postgresql.ENUM(
    "jd_criteria", "peer_feedback", name="reference_kind", create_type=False
)
drift_finding_interaction_kind = postgresql.ENUM(
    "dismiss", "undo", name="drift_finding_interaction_kind", create_type=False
)


def upgrade() -> None:
    reference_kind.create(op.get_bind(), checkfirst=True)
    drift_finding_interaction_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "drift_dismissals",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("reference_kind", reference_kind, nullable=False),
        sa.Column("normalised_criterion", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_drift_dismissals_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drift_dismissals")),
    )
    op.create_index(
        "ix_drift_dismissals_document_reference_criterion",
        "drift_dismissals",
        ["document_id", "reference_kind", "normalised_criterion"],
        unique=False,
    )

    op.create_table(
        "drift_findings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=True),
        sa.Column("reference_kind", reference_kind, nullable=False),
        sa.Column("criterion", sa.Text(), nullable=False),
        sa.Column("normalised_criterion", sa.String(), nullable=False),
        sa.Column("addressed", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("evidence_start", sa.Integer(), nullable=True),
        sa.Column("evidence_end", sa.Integer(), nullable=True),
        sa.Column("suppressed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("suppressed_by_dismissal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_drift_findings_document_id_documents")
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_drift_findings_analysis_run_id_analysis_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["suppressed_by_dismissal_id"],
            ["drift_dismissals.id"],
            name=op.f("fk_drift_findings_suppressed_by_dismissal_id_drift_dismissals"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drift_findings")),
    )
    op.create_index(
        "ix_drift_findings_analysis_run_id", "drift_findings", ["analysis_run_id"], unique=False
    )
    op.create_index(
        "ix_drift_findings_document_reference_criterion",
        "drift_findings",
        ["document_id", "reference_kind", "normalised_criterion"],
        unique=False,
    )
    op.create_index(
        "ix_drift_findings_document_suppressed",
        "drift_findings",
        ["document_id", "suppressed"],
        unique=False,
    )

    op.create_table(
        "drift_interactions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("drift_finding_id", sa.Uuid(), nullable=False),
        sa.Column("kind", drift_finding_interaction_kind, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["drift_finding_id"],
            ["drift_findings.id"],
            name=op.f("fk_drift_interactions_drift_finding_id_drift_findings"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_drift_interactions")),
    )
    op.create_index(
        "ix_drift_interactions_drift_finding_id",
        "drift_interactions",
        ["drift_finding_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("drift_interactions")
    op.drop_table("drift_findings")
    op.drop_table("drift_dismissals")
    drift_finding_interaction_kind.drop(op.get_bind(), checkfirst=True)
    reference_kind.drop(op.get_bind(), checkfirst=True)
