"""add 'superseded' to the analysis_run_status enum

The Layer-2 streaming pipeline (#60) gives a run a third terminal outcome: when a newer
run starts for the same document mid-stream, the older run stops surfacing results but keeps
persisting them (design spec §12). That state is neither 'complete' nor 'failed', so the
enum gains 'superseded'. Append-only on upgrade; the downgrade rebuilds the type without it
(mapping any 'superseded' rows to 'complete', since their flags were persisted and valid).

Revision ID: 0004_add_superseded_run_status
Revises: 0003_extend_disability_lexicon
Create Date: 2026-06-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_add_superseded_run_status"
down_revision: str | None = "0003_extend_disability_lexicon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PG 12+ allows ADD VALUE inside a transaction provided the value is not used in the
    # same transaction (it is not here).
    op.execute("ALTER TYPE analysis_run_status ADD VALUE IF NOT EXISTS 'superseded'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value, so rebuild the type without it.
    op.execute("UPDATE analysis_runs SET status = 'complete' WHERE status = 'superseded'")
    op.execute("ALTER TYPE analysis_run_status RENAME TO analysis_run_status_old")
    op.execute("CREATE TYPE analysis_run_status AS ENUM ('running', 'complete', 'failed')")
    op.execute("ALTER TABLE analysis_runs ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE analysis_runs ALTER COLUMN status TYPE analysis_run_status "
        "USING status::text::analysis_run_status"
    )
    op.execute("ALTER TABLE analysis_runs ALTER COLUMN status SET DEFAULT 'running'")
    op.execute("DROP TYPE analysis_run_status_old")
