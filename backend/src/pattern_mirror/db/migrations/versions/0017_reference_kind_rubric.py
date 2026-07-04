"""add 'promotion_rubric' to the reference_kind enum

A promotion writeup now drifts against its rubric rather than peer feedback (#121), so drift
findings and dismissals record a new ``reference_kind``. Append-only on upgrade; the downgrade
rebuilds the type without it, dropping the promotion-rubric rows (dev-only demo data) first.
The ``reference_kind`` column lives on both ``drift_findings`` and ``drift_dismissals``.

Revision ID: 0017_reference_kind_rubric
Revises: 0016_add_promotion_rubric
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_reference_kind_rubric"
down_revision: str | None = "0016_add_promotion_rubric"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WITHOUT_RUBRIC = "'jd_criteria', 'peer_feedback'"


def upgrade() -> None:
    # PG 12+ allows ADD VALUE inside a transaction provided the value is not used in the
    # same transaction (it is not here).
    op.execute("ALTER TYPE reference_kind ADD VALUE IF NOT EXISTS 'promotion_rubric'")


def downgrade() -> None:
    # PostgreSQL cannot drop an enum value, so rebuild the type without it, clearing the
    # promotion-rubric rows in FK-safe order first (interactions → findings → dismissals).
    op.execute(
        "DELETE FROM drift_interactions WHERE drift_finding_id IN "
        "(SELECT id FROM drift_findings WHERE reference_kind = 'promotion_rubric')"
    )
    op.execute("DELETE FROM drift_findings WHERE reference_kind = 'promotion_rubric'")
    op.execute("DELETE FROM drift_dismissals WHERE reference_kind = 'promotion_rubric'")
    op.execute("ALTER TYPE reference_kind RENAME TO reference_kind_old")
    op.execute(f"CREATE TYPE reference_kind AS ENUM ({_WITHOUT_RUBRIC})")
    for table in ("drift_findings", "drift_dismissals"):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN reference_kind TYPE reference_kind "
            "USING reference_kind::text::reference_kind"
        )
    op.execute("DROP TYPE reference_kind_old")
