"""extend the SG disability lexicon

0002 seeded a single disability term ('able-bodied'), leaving disability the
thinnest MVP category. This adds three more proxies so it has real coverage,
following 0002's frozen-literal + drift-guard-test pattern (lemma_key is the
precomputed lemmatiser output; tests/db/test_seed_lexicon.py re-derives and asserts).

Disability bias rarely appears as a fixed phrase in TAFEP's job-ad examples — it
surfaces as inferring inability from a condition — so these terms are drawn from
the Tripartite Guidelines rather than quoted verbatim, and cite that source (the
citation row seeded in 0002).

Revision ID: 0003_extend_disability_lexicon
Revises: 0002_seed_sg_bias_lexicon
Create Date: 2026-06-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_extend_disability_lexicon"
down_revision: str | None = "0002_seed_sg_bias_lexicon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


bias_category = postgresql.ENUM(
    "gender",
    "age",
    "race",
    "nationality",
    "religion",
    "disability",
    "family_status",
    name="bias_category",
    create_type=False,
)
severity = postgresql.ENUM("low", "medium", "high", name="severity", create_type=False)

_REGION = "SG"
_CATEGORY = "disability"
_TRIPARTITE = "76bcd955-6786-4b88-aefc-6659b5fae3e7"  # citation seeded in 0002

# (term, lemma_key, severity, explanation). Severity follows 0002's rubric:
# explicit health/disability exclusions "high", context-dependent proxies "medium".
_DISABILITY: list[tuple[str, str, str, str]] = [
    (
        "no disabilities",
        "no disability",
        "high",
        "Explicit disability screen; assess ability to do the job, not disability status.",
    ),
    (
        "no health issues",
        "no health issue",
        "high",
        "Health screen unrelated to job needs; TAFEP requires merit-based assessment.",
    ),
    (
        "physically fit and healthy",
        "physically fit and healthy",
        "medium",
        "Fitness ideal beyond stated job needs; state the physical task, not a health profile.",
    ),
]


_dictionaries_table = sa.table(
    "dictionaries",
    sa.column("region_code", sa.String),
    sa.column("category", bias_category),
    sa.column("term", sa.String),
    sa.column("lemma_key", sa.String),
    sa.column("severity", severity),
    sa.column("citation_id", sa.Uuid),
    sa.column("explanation", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(
        _dictionaries_table,
        [
            {
                "region_code": _REGION,
                "category": _CATEGORY,
                "term": term,
                "lemma_key": lemma_key,
                "severity": term_severity,
                "citation_id": _TRIPARTITE,
                "explanation": explanation,
            }
            for (term, lemma_key, term_severity, explanation) in _DISABILITY
        ],
    )


def downgrade() -> None:
    lemma_keys = [lemma_key for (_term, lemma_key, _severity, _explanation) in _DISABILITY]
    op.execute(
        _dictionaries_table.delete().where(
            sa.and_(
                _dictionaries_table.c.region_code == _REGION,
                _dictionaries_table.c.category == _CATEGORY,
                _dictionaries_table.c.lemma_key.in_(lemma_keys),
            )
        )
    )
