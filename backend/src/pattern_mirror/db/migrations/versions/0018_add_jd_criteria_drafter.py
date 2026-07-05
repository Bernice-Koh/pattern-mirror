"""add 'jd_criteria_drafter' to the agent_name enum

JD Studio's Publish step drafts a role's criteria with a Sonnet 4.6 agent whose invocation is
logged to ``agent_runs`` (#122), so the ``agent_name`` enum gains that agent. Append-only on
upgrade; the downgrade rebuilds the type without it, first dropping any ``agent_runs`` rows that
recorded a draft (dev-only audit data).

Revision ID: 0018_add_jd_criteria_drafter
Revises: 0017_reference_kind_rubric
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_add_jd_criteria_drafter"
down_revision: str | None = "0017_reference_kind_rubric"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WITHOUT_DRAFTER = (
    "'contextual_pass', 'judge', 'recommendations', 'drift', "
    "'proposer', 'skeptic', 'categorizer', 'citation'"
)


def upgrade() -> None:
    # PG 12+ allows ADD VALUE inside a transaction provided the value is not used in the
    # same transaction (it is not here).
    op.execute("ALTER TYPE agent_name ADD VALUE IF NOT EXISTS 'jd_criteria_drafter'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value, so rebuild the type without it. The audit rows that
    # used it have no meaningful fallback agent, so they are dropped (dev-only data).
    op.execute("DELETE FROM agent_runs WHERE agent_name = 'jd_criteria_drafter'")
    op.execute("ALTER TYPE agent_name RENAME TO agent_name_old")
    op.execute(f"CREATE TYPE agent_name AS ENUM ({_WITHOUT_DRAFTER})")
    op.execute(
        "ALTER TABLE agent_runs ALTER COLUMN agent_name TYPE agent_name "
        "USING agent_name::text::agent_name"
    )
    op.execute("DROP TYPE agent_name_old")
