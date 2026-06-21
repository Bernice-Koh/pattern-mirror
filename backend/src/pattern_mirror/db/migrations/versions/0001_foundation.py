"""foundation schema

The engine core plus JD Studio: reference data, identity/subjects, documents,
the bias engine (flags + dismissals), the dictionary lexicon, and the agent-run
audit log. Seeds the SEA region lookup (only SG carries a lexicon in MVP).

Native enum types are created once up front and referenced with
``create_type=False`` so a type shared by two tables (``bias_category`` on both
``flags`` and ``dictionaries``) is not created twice. ``dictionaries.origin_candidate_id``
and ``agent_runs.candidate_id`` are intentionally deferred to migration 0005,
which adds the ``dictionary_candidates`` table they reference.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


citation_source_type = postgresql.ENUM(
    "tafep", "academic", "regulatory", "other", name="citation_source_type", create_type=False
)
user_role = postgresql.ENUM("manager", "hr", name="user_role", create_type=False)
subject_type = postgresql.ENUM("candidate", "employee", name="subject_type", create_type=False)
doc_type = postgresql.ENUM("jd", "feedback", "promotion", name="doc_type", create_type=False)
document_status = postgresql.ENUM("draft", "submitted", name="document_status", create_type=False)
analysis_trigger = postgresql.ENUM(
    "typing_pause", "save", "submit", "recheck", name="analysis_trigger", create_type=False
)
analysis_run_status = postgresql.ENUM(
    "running", "complete", "failed", name="analysis_run_status", create_type=False
)
flag_source_stage = postgresql.ENUM(
    "dictionary", "contextual", name="flag_source_stage", create_type=False
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
flag_scope = postgresql.ENUM("general", "role_specific", name="flag_scope", create_type=False)
flag_verdict = postgresql.ENUM(
    "acceptable",
    "acceptable_with_justification",
    "unacceptable",
    name="flag_verdict",
    create_type=False,
)
severity = postgresql.ENUM("low", "medium", "high", name="severity", create_type=False)
agent_name = postgresql.ENUM(
    "contextual_pass",
    "judge",
    "recommendations",
    "proposer",
    "skeptic",
    "categorizer",
    "citation",
    name="agent_name",
    create_type=False,
)

_ENUM_TYPES = (
    citation_source_type,
    user_role,
    subject_type,
    doc_type,
    document_status,
    analysis_trigger,
    analysis_run_status,
    flag_source_stage,
    bias_category,
    flag_scope,
    flag_verdict,
    severity,
    agent_name,
)

_REGION_SEED = [
    {"code": "SG", "name": "Singapore"},
    {"code": "MY", "name": "Malaysia"},
    {"code": "ID", "name": "Indonesia"},
    {"code": "TH", "name": "Thailand"},
    {"code": "PH", "name": "Philippines"},
    {"code": "VN", "name": "Vietnam"},
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in _ENUM_TYPES:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "citations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_type", citation_source_type, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("publication_year", sa.SmallInteger(), nullable=True),
        sa.Column("finding", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_citations")),
    )
    op.create_table(
        "regions",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_regions")),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_type", subject_type, nullable=False),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("external_ref", sa.String(), nullable=True),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("age_band", sa.String(), nullable=True),
        sa.Column("hired", sa.Boolean(), nullable=True),
        sa.Column("resume_blob_ref", sa.String(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("external_user_id", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("avatar_blob_ref", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("external_user_id", name=op.f("uq_users_external_user_id")),
    )
    op.create_table(
        "dictionaries",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("region_code", sa.String(length=8), nullable=False),
        sa.Column("category", bias_category, nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("lemma_key", sa.String(), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("citation_id", sa.Uuid(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["citation_id"], ["citations.id"], name=op.f("fk_dictionaries_citation_id_citations")
        ),
        sa.ForeignKeyConstraint(
            ["region_code"], ["regions.code"], name=op.f("fk_dictionaries_region_code_regions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionaries")),
        sa.UniqueConstraint(
            "region_code",
            "lemma_key",
            "category",
            name="uq_dictionaries_region_code_lemma_key_category",
        ),
    )
    op.create_index(
        "ix_dictionaries_region_code_active",
        "dictionaries",
        ["region_code", "active"],
        unique=False,
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("doc_type", doc_type, nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("role_title", sa.String(), nullable=True),
        sa.Column("status", document_status, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("submitted_content", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reference_jd_id", sa.Uuid(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_documents_owner_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["reference_jd_id"],
            ["documents.id"],
            name=op.f("fk_documents_reference_jd_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_documents_subject_id_subjects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(
        "ix_documents_owner_id_created_at", "documents", ["owner_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_documents_owner_id_doc_type", "documents", ["owner_id", "doc_type"], unique=False
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column(
            "granted_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users")
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_user_roles")),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("trigger", analysis_trigger, nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status", analysis_run_status, server_default=sa.text("'running'"), nullable=False
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_analysis_runs_document_id_documents")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_runs")),
    )
    op.create_index(
        op.f("ix_analysis_runs_document_id"), "analysis_runs", ["document_id"], unique=False
    )
    op.create_table(
        "flag_dismissals",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column("normalised_span", sa.String(), nullable=False),
        sa.Column("sentence_fingerprint", sa.String(length=64), nullable=False),
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
            name=op.f("fk_flag_dismissals_document_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["dictionaries.id"], name=op.f("fk_flag_dismissals_rule_id_dictionaries")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flag_dismissals")),
    )
    op.create_index(
        "ix_flag_dismissals_document_id_rule_id_normalised_span",
        "flag_dismissals",
        ["document_id", "rule_id", "normalised_span"],
        unique=False,
    )
    op.create_table(
        "flags",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_stage", flag_source_stage, nullable=False),
        sa.Column("dictionary_entry_id", sa.Uuid(), nullable=True),
        sa.Column("citation_id", sa.Uuid(), nullable=True),
        sa.Column("category", bias_category, nullable=False),
        sa.Column("scope", flag_scope, nullable=False),
        sa.Column("verdict", flag_verdict, nullable=True),
        sa.Column("raw_span", sa.Text(), nullable=False),
        sa.Column("normalised_span", sa.String(), nullable=False),
        sa.Column("sentence_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("rationale", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("judge_confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("judge_hallucination_risk", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("suppressed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("suppressed_by_dismissal_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_flags_analysis_run_id_analysis_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["citation_id"], ["citations.id"], name=op.f("fk_flags_citation_id_citations")
        ),
        sa.ForeignKeyConstraint(
            ["dictionary_entry_id"],
            ["dictionaries.id"],
            name=op.f("fk_flags_dictionary_entry_id_dictionaries"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_flags_document_id_documents")
        ),
        sa.ForeignKeyConstraint(
            ["suppressed_by_dismissal_id"],
            ["flag_dismissals.id"],
            name=op.f("fk_flags_suppressed_by_dismissal_id_flag_dismissals"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flags")),
    )
    op.create_index(op.f("ix_flags_analysis_run_id"), "flags", ["analysis_run_id"], unique=False)
    op.create_index("ix_flags_category", "flags", ["category"], unique=False)
    op.create_index("ix_flags_created_at", "flags", ["created_at"], unique=False)
    op.create_index(
        "ix_flags_document_id_normalised_span_sentence_fingerprint",
        "flags",
        ["document_id", "normalised_span", "sentence_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_flags_document_id_suppressed", "flags", ["document_id", "suppressed"], unique=False
    )
    op.create_index("ix_flags_verdict", "flags", ["verdict"], unique=False)
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_name", agent_name, nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("flag_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name=op.f("fk_agent_runs_analysis_run_id_analysis_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], name=op.f("fk_agent_runs_document_id_documents")
        ),
        sa.ForeignKeyConstraint(
            ["flag_id"], ["flags.id"], name=op.f("fk_agent_runs_flag_id_flags")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(op.f("ix_agent_runs_agent_name"), "agent_runs", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_runs_document_id"), "agent_runs", ["document_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_flag_id"), "agent_runs", ["flag_id"], unique=False)

    regions = sa.table("regions", sa.column("code", sa.String), sa.column("name", sa.String))
    op.bulk_insert(regions, _REGION_SEED)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_runs_flag_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_document_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_name"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_flags_verdict", table_name="flags")
    op.drop_index("ix_flags_document_id_suppressed", table_name="flags")
    op.drop_index("ix_flags_document_id_normalised_span_sentence_fingerprint", table_name="flags")
    op.drop_index("ix_flags_created_at", table_name="flags")
    op.drop_index("ix_flags_category", table_name="flags")
    op.drop_index(op.f("ix_flags_analysis_run_id"), table_name="flags")
    op.drop_table("flags")
    op.drop_index(
        "ix_flag_dismissals_document_id_rule_id_normalised_span", table_name="flag_dismissals"
    )
    op.drop_table("flag_dismissals")
    op.drop_index(op.f("ix_analysis_runs_document_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_table("user_roles")
    op.drop_index("ix_documents_owner_id_doc_type", table_name="documents")
    op.drop_index("ix_documents_owner_id_created_at", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_dictionaries_region_code_active", table_name="dictionaries")
    op.drop_table("dictionaries")
    op.drop_table("users")
    op.drop_table("subjects")
    op.drop_table("regions")
    op.drop_table("citations")

    bind = op.get_bind()
    for enum_type in _ENUM_TYPES:
        enum_type.drop(bind, checkfirst=True)
