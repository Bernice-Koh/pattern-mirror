"""Native-enum value sets and their reusable SQLAlchemy column types.

Each set is a ``StrEnum`` (the Python-side domain) paired with a ``sqlalchemy.Enum``
bound to a stable PostgreSQL type name. Columns that share a type — ``bias_category``
on both ``flags`` and ``dictionaries`` — reference the *same* instance so there is one
definition, not two that can drift.

``create_type=False``: the enum types are created (and dropped) explicitly in the
Alembic migration, not implicitly by table DDL. This keeps creation order under the
migration's control and avoids "type already exists" errors when a shared type is
referenced by more than one table.
"""

from enum import StrEnum, auto

from sqlalchemy import Enum as SAEnum


class CitationSourceType(StrEnum):
    tafep = auto()
    academic = auto()
    regulatory = auto()
    other = auto()


class UserRole(StrEnum):
    manager = auto()
    hr = auto()


class SubjectType(StrEnum):
    candidate = auto()
    employee = auto()


class DocType(StrEnum):
    jd = auto()
    feedback = auto()
    promotion = auto()


class DocumentStatus(StrEnum):
    draft = auto()
    submitted = auto()


class AnalysisTrigger(StrEnum):
    typing_pause = auto()
    save = auto()
    submit = auto()
    recheck = auto()


class AnalysisRunStatus(StrEnum):
    running = auto()
    complete = auto()
    failed = auto()
    # A newer run for the same document started before this one finished streaming; it
    # stopped surfacing results but kept persisting them (design spec §12).
    superseded = auto()


class FlagSourceStage(StrEnum):
    dictionary = auto()
    contextual = auto()


class BiasCategory(StrEnum):
    gender = auto()
    age = auto()
    race = auto()
    nationality = auto()
    religion = auto()
    disability = auto()
    family_status = auto()


class FlagScope(StrEnum):
    general = auto()
    role_specific = auto()


class FlagVerdict(StrEnum):
    acceptable = auto()
    acceptable_with_justification = auto()
    unacceptable = auto()


class FlagInteractionKind(StrEnum):
    accept = auto()
    dismiss = auto()
    # Reverses a prior dismiss; the absence of any interaction is "ignored" (design spec §13).
    undo = auto()


class AgentName(StrEnum):
    contextual_pass = auto()
    judge = auto()
    recommendations = auto()
    proposer = auto()
    skeptic = auto()
    categorizer = auto()
    citation = auto()


def _pg_enum(python_enum: type[StrEnum], name: str) -> SAEnum:
    """Build a native PG enum column type whose values are the enum's string values."""
    return SAEnum(
        python_enum,
        name=name,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
        create_type=False,
    )


citation_source_type_enum = _pg_enum(CitationSourceType, "citation_source_type")
user_role_enum = _pg_enum(UserRole, "user_role")
subject_type_enum = _pg_enum(SubjectType, "subject_type")
doc_type_enum = _pg_enum(DocType, "doc_type")
document_status_enum = _pg_enum(DocumentStatus, "document_status")
analysis_trigger_enum = _pg_enum(AnalysisTrigger, "analysis_trigger")
analysis_run_status_enum = _pg_enum(AnalysisRunStatus, "analysis_run_status")
flag_source_stage_enum = _pg_enum(FlagSourceStage, "flag_source_stage")
bias_category_enum = _pg_enum(BiasCategory, "bias_category")
flag_scope_enum = _pg_enum(FlagScope, "flag_scope")
flag_verdict_enum = _pg_enum(FlagVerdict, "flag_verdict")
flag_interaction_kind_enum = _pg_enum(FlagInteractionKind, "flag_interaction_kind")
agent_name_enum = _pg_enum(AgentName, "agent_name")
