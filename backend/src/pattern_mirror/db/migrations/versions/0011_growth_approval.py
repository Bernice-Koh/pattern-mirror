"""stage explanation and decision columns on pending dictionary additions

The HR approval path (#90) materialises a live ``dictionaries`` row from a queued
addition, which needs an ``explanation`` the queue does not yet carry; and
reject/defer, which create no row, need somewhere durable to record who decided
and when. Both land on ``pending_dictionary_additions``. The table only ever holds
rows written by the live growth batch (never a migration or seed), so it is empty
in every deployed database — the NOT NULL ``explanation`` needs no backfill.

Revision ID: 0011_growth_approval
Revises: 0010_dictionary_growth_schema
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_growth_approval"
down_revision: str | None = "0010_dictionary_growth_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pending_dictionary_additions", sa.Column("explanation", sa.Text(), nullable=False)
    )
    op.add_column(
        "pending_dictionary_additions", sa.Column("decided_by", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "pending_dictionary_additions",
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_pending_dictionary_additions_decided_by_users"),
        "pending_dictionary_additions",
        "users",
        ["decided_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_pending_dictionary_additions_decided_by_users"),
        "pending_dictionary_additions",
        type_="foreignkey",
    )
    op.drop_column("pending_dictionary_additions", "decided_at")
    op.drop_column("pending_dictionary_additions", "decided_by")
    op.drop_column("pending_dictionary_additions", "explanation")
