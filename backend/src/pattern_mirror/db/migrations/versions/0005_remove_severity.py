"""remove the unused severity signal

Severity fed no engine logic (the Judge scores confidence) and was rendered nowhere; it is
dropped end to end (ADR 0009). This removes the ``dictionaries.severity`` column and the
``severity`` enum type created in 0001. The 0001–0003 seed migrations still set the column
transiently on a fresh build before this revision drops it — released history is left
untouched. Downgrade recreates the type and a nullable column; the seeded values are not
restored.

Revision ID: 0005_remove_severity
Revises: 0004_add_superseded_run_status
Create Date: 2026-06-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_remove_severity"
down_revision: str | None = "0004_add_superseded_run_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


severity = postgresql.ENUM("low", "medium", "high", name="severity", create_type=False)


def upgrade() -> None:
    op.drop_column("dictionaries", "severity")
    severity.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    severity.create(bind, checkfirst=True)
    # Nullable: the originally-seeded values cannot be reconstructed on downgrade.
    op.add_column("dictionaries", sa.Column("severity", severity, nullable=True))
