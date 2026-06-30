"""add the dictionary-growth persistence: proposals, pending queue, provenance

The schema foundation for the four-agent growth loop (#87): ``dictionary_proposals``
records every evaluated phrase and its found citation (agents attach via
``agent_runs.proposal_id``); ``pending_dictionary_additions`` queues the ones that
clear the 3-of-4 gate for monthly HR approval. ``dictionaries`` gains
``last_updated_by`` and ``source_proposal_id`` provenance, null on seeded rows.
Schema only — no trigger, agents, or approval logic.

Revision ID: 0010_dictionary_growth_schema
Revises: 0009_add_calibration_runs
Create Date: 2026-07-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_dictionary_growth_schema"
down_revision: str | None = "0009_add_calibration_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

dictionary_addition_status = postgresql.ENUM(
    "pending",
    "approved",
    "rejected",
    "deferred",
    name="dictionary_addition_status",
    create_type=False,
)
# Already created in 0001; referenced here, never re-created.
bias_category = postgresql.ENUM(name="bias_category", create_type=False)


def upgrade() -> None:
    dictionary_addition_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "dictionary_proposals",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("lemma_key", sa.String(), nullable=False),
        sa.Column("citation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["citation_id"],
            ["citations.id"],
            name=op.f("fk_dictionary_proposals_citation_id_citations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary_proposals")),
    )
    op.create_table(
        "pending_dictionary_additions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("phrase", sa.Text(), nullable=False),
        sa.Column("lemma_key", sa.String(), nullable=False),
        sa.Column("proposed_category", bias_category, nullable=False),
        sa.Column(
            "status",
            dictionary_addition_status,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["dictionary_proposals.id"],
            name=op.f("fk_pending_dictionary_additions_proposal_id_dictionary_proposals"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_dictionary_additions")),
    )
    op.add_column("agent_runs", sa.Column("proposal_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_agent_runs_proposal_id_dictionary_proposals"),
        "agent_runs",
        "dictionary_proposals",
        ["proposal_id"],
        ["id"],
    )
    op.create_index("ix_agent_runs_proposal_id", "agent_runs", ["proposal_id"], unique=False)
    op.add_column("dictionaries", sa.Column("last_updated_by", sa.Uuid(), nullable=True))
    op.add_column("dictionaries", sa.Column("source_proposal_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_dictionaries_last_updated_by_users"),
        "dictionaries",
        "users",
        ["last_updated_by"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_dictionaries_source_proposal_id_dictionary_proposals"),
        "dictionaries",
        "dictionary_proposals",
        ["source_proposal_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_dictionaries_source_proposal_id_dictionary_proposals"),
        "dictionaries",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_dictionaries_last_updated_by_users"), "dictionaries", type_="foreignkey"
    )
    op.drop_column("dictionaries", "source_proposal_id")
    op.drop_column("dictionaries", "last_updated_by")
    op.drop_index("ix_agent_runs_proposal_id", table_name="agent_runs")
    op.drop_constraint(
        op.f("fk_agent_runs_proposal_id_dictionary_proposals"), "agent_runs", type_="foreignkey"
    )
    op.drop_column("agent_runs", "proposal_id")
    op.drop_table("pending_dictionary_additions")
    op.drop_table("dictionary_proposals")
    dictionary_addition_status.drop(op.get_bind(), checkfirst=True)
