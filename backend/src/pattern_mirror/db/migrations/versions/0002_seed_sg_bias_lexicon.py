"""seed the SG bias lexicon

Populates ``citations`` and ``dictionaries`` for all seven MVP bias categories,
every entry cited and scoped to ``region_code = 'SG'``.

Seed data is inline frozen literals: a migration must not import application code
whose behaviour can drift. ``lemma_key`` is the precomputed output of
``engine.lemmatiser``; ``tests/db/test_seed_lexicon.py`` re-derives each key via the
live utility and asserts equality, so model drift fails loudly here.

Revision ID: 0002_seed_sg_bias_lexicon
Revises: 0001_foundation
Create Date: 2026-06-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_seed_sg_bias_lexicon"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Enum types already exist (created in 0001); reference them without re-creating.
citation_source_type = postgresql.ENUM(
    "tafep", "academic", "regulatory", "other", name="citation_source_type", create_type=False
)
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

# Pinned so dictionary rows can reference them and downgrade can target exactly these rows.
_TRIPARTITE = "76bcd955-6786-4b88-aefc-6659b5fae3e7"
_JOB_AD = "37877406-5ff9-499a-a4d3-f5ae2ce59690"
_PREGNANCY = "76569bc1-52d4-4169-8d45-b428a9b0df26"
_RELIGIOUS = "cdef1383-ee1f-4e67-8cba-1210793a63f8"

_CITATIONS: list[dict[str, str]] = [
    {
        "id": _TRIPARTITE,
        "source_type": "tafep",
        "title": "Tripartite Guidelines on Fair Employment Practices",
        "reference": "https://www.tafep.sg/publication/tripartite-guidelines-fair-employment-practices",
        "finding": (
            "Recruit and select on merit, regardless of age, race, gender, religion, "
            "marital status and family responsibilities, or disability."
        ),
    },
    {
        "id": _JOB_AD,
        "source_type": "tafep",
        "title": "What is a Discriminatory Job Advertisement?",
        "reference": "https://www.tafep.sg/fair-hiring-practices",
        "finding": (
            "Job advertisements must state only job-related criteria and omit words signalling "
            "a preference on a protected characteristic, including indirect phrasing."
        ),
    },
    {
        "id": _PREGNANCY,
        "source_type": "tafep",
        "title": "Tripartite Guidelines on Pregnancy and Maternity",
        "reference": "https://www.tafep.sg",
        "finding": (
            "Pregnancy and maternity leave must not be used as grounds for adverse hiring or "
            "promotion decisions."
        ),
    },
    {
        "id": _RELIGIOUS,
        "source_type": "tafep",
        "title": "Tripartite Guide on Religious Accommodation",
        "reference": "https://www.tafep.sg",
        "finding": "Reasonably accommodate religious practices before taking adverse action.",
    },
]

# (category, term, lemma_key, severity, citation_id, explanation).
# Severity: explicit exclusions "high", context-dependent proxies "medium".
_LEXICON: list[tuple[str, str, str, str, str, str]] = [
    (
        "gender",
        "masculine",
        "masculine",
        "high",
        _TRIPARTITE,
        "Gender-coded leadership trait; TAFEP requires selection on merit, not gender.",
    ),
    (
        "gender",
        "preferably female",
        "preferably female",
        "high",
        _JOB_AD,
        "States a gender preference TAFEP lists as a phrase to avoid in job advertisements.",
    ),
    (
        "gender",
        "female working environment",
        "female working environment",
        "medium",
        _JOB_AD,
        "Signals a gender-based environment; TAFEP lists it among job-ad phrases to avoid.",
    ),
    (
        "age",
        "young",
        "young",
        "high",
        _JOB_AD,
        "Age proxy; TAFEP bars 'young/youthful working environment' from job advertisements.",
    ),
    (
        "age",
        "youthful",
        "youthful",
        "high",
        _JOB_AD,
        "Age proxy; TAFEP bars 'young/youthful working environment' from job advertisements.",
    ),
    (
        "age",
        "digital native",
        "digital native",
        "medium",
        _JOB_AD,
        "Coded age preference for younger workers; skills can be acquired at any age.",
    ),
    (
        "age",
        "mature",
        "mature",
        "medium",
        _TRIPARTITE,
        "Age proxy that can screen workers by age; assess experience in years, not age.",
    ),
    (
        "age",
        "seasoned",
        "season",
        "medium",
        _TRIPARTITE,
        "Age-coded experience proxy; TAFEP requires merit-based assessment, not age signals.",
    ),
    (
        "race",
        "chinese only",
        "chinese only",
        "high",
        _JOB_AD,
        "Race-based exclusion; TAFEP lists 'Chinese/Malay/Indian only' as a phrase to avoid.",
    ),
    (
        "race",
        "malay only",
        "malay only",
        "high",
        _JOB_AD,
        "Race-based exclusion; TAFEP lists 'Chinese/Malay/Indian only' as a phrase to avoid.",
    ),
    (
        "race",
        "indian only",
        "indian only",
        "high",
        _JOB_AD,
        "Race-based exclusion; TAFEP lists 'Chinese/Malay/Indian only' as a phrase to avoid.",
    ),
    (
        "race",
        "chinese-speaking environment",
        "chinese speak environment",
        "medium",
        _JOB_AD,
        "Language-as-race proxy; TAFEP lists '...speaking environment' among phrases to avoid.",
    ),
    (
        "nationality",
        "foreigner",
        "foreigner",
        "high",
        _JOB_AD,
        "Signals a nationality preference; TAFEP bars phrases preferring non-Singaporeans.",
    ),
    (
        "nationality",
        "non-singaporean",
        "non singaporean",
        "high",
        _JOB_AD,
        "Nationality preference TAFEP lists as a phrase employers must not use.",
    ),
    (
        "nationality",
        "work pass holder",
        "work pass holder",
        "medium",
        _JOB_AD,
        "Pass-type preference (e.g. 'EP/S Pass holders preferred') signals nationality bias.",
    ),
    (
        "religion",
        "christian only",
        "christian only",
        "high",
        _JOB_AD,
        "Religion-based exclusion; TAFEP lists '[religion] only' as a phrase to avoid.",
    ),
    (
        "religion",
        "buddhist only",
        "buddhist only",
        "high",
        _JOB_AD,
        "Religion-based exclusion; TAFEP lists '[religion] only' as a phrase to avoid.",
    ),
    (
        "religion",
        "muslim only",
        "muslim only",
        "high",
        _JOB_AD,
        "Religion-based exclusion; TAFEP lists '[religion] only' as a phrase to avoid.",
    ),
    (
        "religion",
        "hindu only",
        "hindu only",
        "high",
        _JOB_AD,
        "Religion-based exclusion; TAFEP lists '[religion] only' as a phrase to avoid.",
    ),
    (
        "religion",
        "prayer break",
        "prayer break",
        "medium",
        _RELIGIOUS,
        "Frames religious observance as disruption; accommodation precedes adverse action.",
    ),
    (
        "disability",
        "able-bodied",
        "able bodied",
        "medium",
        _TRIPARTITE,
        "Screens on physical identity, not job needs; inferred (no verbatim TAFEP example).",
    ),
    (
        "family_status",
        "bachelor",
        "bachelor",
        "medium",
        _TRIPARTITE,
        "Marital-status proxy ('work like a bachelor'); TAFEP bars selection on marital status.",
    ),
    (
        "family_status",
        "family commitment",
        "family commitment",
        "high",
        _JOB_AD,
        "Family-responsibility screen; TAFEP bars 'without family commitments', even indirectly.",
    ),
    (
        "family_status",
        "newly married",
        "newly marry",
        "medium",
        _TRIPARTITE,
        "Marital-status proxy used to predict flight risk; TAFEP requires individual assessment.",
    ),
    (
        "family_status",
        "pregnant",
        "pregnant",
        "high",
        _PREGNANCY,
        "Pregnancy must not affect hiring or promotion decisions under TAFEP guidance.",
    ),
    (
        "family_status",
        "maternity leave",
        "maternity leave",
        "high",
        _PREGNANCY,
        "Anticipated maternity leave must not drive employment decisions under TAFEP guidance.",
    ),
]


_citations_table = sa.table(
    "citations",
    sa.column("id", sa.Uuid),
    sa.column("source_type", citation_source_type),
    sa.column("title", sa.Text),
    sa.column("reference", sa.Text),
    sa.column("finding", sa.Text),
)

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
    op.bulk_insert(_citations_table, _CITATIONS)
    op.bulk_insert(
        _dictionaries_table,
        [
            {
                "region_code": _REGION,
                "category": category,
                "term": term,
                "lemma_key": lemma_key,
                "severity": term_severity,
                "citation_id": citation_id,
                "explanation": explanation,
            }
            for (category, term, lemma_key, term_severity, citation_id, explanation) in _LEXICON
        ],
    )


def downgrade() -> None:
    citation_ids = [citation["id"] for citation in _CITATIONS]
    op.execute(
        _dictionaries_table.delete().where(_dictionaries_table.c.citation_id.in_(citation_ids))
    )
    op.execute(_citations_table.delete().where(_citations_table.c.id.in_(citation_ids)))
