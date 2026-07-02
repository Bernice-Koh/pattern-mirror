"""add 'drift' to the agent_name enum

The drift agent (#64) runs alongside the five-stage bias pipeline and logs each
invocation to ``agent_runs``, whose ``agent_name`` column is a native enum. It gains
'drift'. Append-only on upgrade; the downgrade rebuilds the type without it (mapping any
'drift' rows to null-safe removal is unneeded — the table only ever holds live runs).

Revision ID: 0012_add_drift_agent_name
Revises: 0011_growth_approval
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012_add_drift_agent_name"
down_revision: str | None = "0011_growth_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WITHOUT_DRIFT = (
    "'contextual_pass', 'judge', 'recommendations', "
    "'proposer', 'skeptic', 'categorizer', 'citation'"
)


def upgrade() -> None:
    # PG 12+ allows ADD VALUE inside a transaction provided the value is not used in the
    # same transaction (it is not here).
    op.execute("ALTER TYPE agent_name ADD VALUE IF NOT EXISTS 'drift'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value, so rebuild the type without it.
    op.execute("DELETE FROM agent_runs WHERE agent_name = 'drift'")
    op.execute("ALTER TYPE agent_name RENAME TO agent_name_old")
    op.execute(f"CREATE TYPE agent_name AS ENUM ({_WITHOUT_DRIFT})")
    op.execute(
        "ALTER TABLE agent_runs ALTER COLUMN agent_name TYPE agent_name "
        "USING agent_name::text::agent_name"
    )
    op.execute("DROP TYPE agent_name_old")
