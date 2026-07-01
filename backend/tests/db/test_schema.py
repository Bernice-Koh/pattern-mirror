"""Schema tests: the migration at head produces the tables and columns the AC names.

These assert against the live, migrated test database via reflection, plus one
ORM round-trip that exercises the mapped relationships and foreign keys end to end.
"""

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagDismissal
from pattern_mirror.models.enums import (
    AgentName,
    AnalysisTrigger,
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
    DocType,
    FlagScope,
    FlagSourceStage,
    SubjectType,
    UserRole,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.reference import Citation, Region

pytestmark = pytest.mark.db

_AC_CORE_TABLES = {"users", "documents", "flags", "flag_dismissals", "dictionaries", "citations"}
_ALL_FOUNDATION_TABLES = {
    "regions",
    "citations",
    "dictionaries",
    "users",
    "user_roles",
    "subjects",
    "documents",
    "analysis_runs",
    "flags",
    "flag_dismissals",
    "agent_runs",
    "dictionary_proposals",
    "pending_dictionary_additions",
}


def test_acceptance_core_tables_exist(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())

    assert _AC_CORE_TABLES.issubset(tables)


def test_all_foundation_tables_exist(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())

    assert _ALL_FOUNDATION_TABLES.issubset(tables)


def test_calibration_runs_table_carries_the_dashboard_metrics(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    columns = {col["name"]: col for col in inspector.get_columns("calibration_runs")}

    expected = {"agreement", "ece", "brier", "scored_count", "per_stage", "created_at"}
    assert expected.issubset(columns)
    assert columns["agreement"]["nullable"] is True
    assert columns["scored_count"]["nullable"] is False
    assert columns["per_stage"]["nullable"] is False


def test_flags_carry_provenance_reference_scores_and_suppressed(migrated_engine: Engine) -> None:
    columns = {col["name"]: col for col in inspect(migrated_engine).get_columns("flags")}

    assert columns["source_stage"]["nullable"] is False
    assert columns["dictionary_entry_id"]["nullable"] is True
    assert columns["citation_id"]["nullable"] is True
    assert columns["judge_confidence"]["nullable"] is True
    assert "judge_hallucination_risk" not in columns
    assert columns["suppressed"]["nullable"] is False


def test_flag_dismissals_store_the_signature(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    columns = {col["name"]: col for col in inspector.get_columns("flag_dismissals")}

    assert {"document_id", "rule_id", "normalised_span", "sentence_fingerprint"}.issubset(columns)
    # rule_id is null for contextual-stage dismissals; the span + fingerprint that
    # make the suppression signature reliable are not nullable.
    assert columns["rule_id"]["nullable"] is True
    assert columns["normalised_span"]["nullable"] is False
    assert columns["sentence_fingerprint"]["nullable"] is False

    index_columns = {
        tuple(index["column_names"]) for index in inspector.get_indexes("flag_dismissals")
    }
    assert ("document_id", "rule_id", "normalised_span") in index_columns


def test_dictionaries_are_region_scoped(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    columns = {col["name"] for col in inspector.get_columns("dictionaries")}
    foreign_keys = inspector.get_foreign_keys("dictionaries")

    assert "region_code" in columns
    assert any(
        fk["referred_table"] == "regions" and fk["constrained_columns"] == ["region_code"]
        for fk in foreign_keys
    )


def test_regions_seed_is_the_sea_jurisdiction_set(db_session: Session) -> None:
    codes = set(db_session.scalars(select(Region.code)).all())

    assert codes == {"SG", "MY", "ID", "TH", "PH", "VN"}
    singapore = db_session.get(Region, "SG")
    assert singapore is not None
    assert singapore.active is True


def test_orm_round_trip_links_the_engine_graph(db_session: Session) -> None:
    manager = User(
        external_user_id="ext-mock-1",
        legal_name="Mock Manager",
        email="mock.manager@example.test",
    )
    manager.roles.append(UserRoleAssignment(role=UserRole.manager))
    candidate = Subject(subject_type=SubjectType.candidate, legal_name="Mock Candidate")
    document = Document(owner=manager, doc_type=DocType.feedback, subject=candidate, content="text")
    run = AnalysisRun(document=document, trigger=AnalysisTrigger.submit, content_hash="0" * 64)
    flag = Flag(
        document=document,
        analysis_run=run,
        source_stage=FlagSourceStage.contextual,
        category=BiasCategory.gender,
        scope=FlagScope.general,
        raw_span="aggressive",
        normalised_span="aggressive",
        sentence_fingerprint="f" * 64,
        rationale={"reason": "synthetic"},
    )
    dismissal = FlagDismissal(
        document=document, normalised_span="aggressive", sentence_fingerprint="f" * 64
    )
    flag.suppressed_by_dismissal = dismissal
    flag.suppressed = True
    db_session.add(manager)
    db_session.flush()
    db_session.expire_all()

    stored_flag = db_session.scalars(select(Flag)).one()
    assert stored_flag.document.owner.email == "mock.manager@example.test"
    assert stored_flag.analysis_run is not None
    assert stored_flag.document.subject is not None
    assert stored_flag.document.subject.subject_type is SubjectType.candidate
    assert stored_flag.suppressed_by_dismissal is not None
    assert stored_flag in stored_flag.suppressed_by_dismissal.suppressed_flags


def test_pending_additions_queue_carries_the_hr_fields(migrated_engine: Engine) -> None:
    columns = {
        col["name"]: col
        for col in inspect(migrated_engine).get_columns("pending_dictionary_additions")
    }

    assert {"proposal_id", "phrase", "lemma_key", "proposed_category", "status"}.issubset(columns)
    assert columns["proposal_id"]["nullable"] is False
    assert columns["status"]["nullable"] is False
    assert columns["proposed_category"]["nullable"] is False
    # Severity was dropped end to end (ADR 0009); a grown entry proposes a category only.
    assert "proposed_severity" not in columns


def test_dictionaries_carry_growth_provenance(migrated_engine: Engine) -> None:
    columns = {col["name"]: col for col in inspect(migrated_engine).get_columns("dictionaries")}

    assert columns["last_updated_by"]["nullable"] is True
    assert columns["source_proposal_id"]["nullable"] is True
    # "When" is the existing updated_at; no second timestamp column.
    assert "last_updated_at" not in columns


def test_agent_runs_link_to_a_growth_proposal(migrated_engine: Engine) -> None:
    columns = {col["name"]: col for col in inspect(migrated_engine).get_columns("agent_runs")}

    assert "proposal_id" in columns
    assert columns["proposal_id"]["nullable"] is True


def test_orm_round_trip_links_the_growth_graph(db_session: Session) -> None:
    approver = User(
        external_user_id="ext-hr-1",
        legal_name="Mock HR",
        email="mock.hr@example.test",
    )
    citation = Citation(
        source_type=CitationSourceType.academic,
        title="Synthetic study",
        reference="doi:synthetic",
    )
    proposal = DictionaryProposal(phrase="culture fit", lemma_key="culture fit", citation=citation)
    agent_names = (
        AgentName.proposer,
        AgentName.skeptic,
        AgentName.categorizer,
        AgentName.citation,
    )
    arguments = [
        AgentRun(agent_name=name, model="claude-mock", input={}, output={}, proposal=proposal)
        for name in agent_names
    ]
    queued = PendingDictionaryAddition(
        proposal=proposal,
        phrase="culture fit",
        lemma_key="culture fit",
        proposed_category=BiasCategory.age,
        explanation="Youth-coded phrasing that deters older candidates.",
    )
    db_session.add_all([approver, *arguments, queued])
    db_session.flush()  # populate server-generated ids before the column-only FK is set

    live_entry = Dictionary(
        region_code="SG",
        category=BiasCategory.age,
        term="culture fit",
        lemma_key="culture fit",
        citation=citation,
        explanation="synthetic",
        last_updated_by=approver.id,
        source_proposal=proposal,
    )
    db_session.add(live_entry)
    db_session.flush()
    db_session.expire_all()

    stored = db_session.scalars(
        select(PendingDictionaryAddition).where(PendingDictionaryAddition.phrase == "culture fit")
    ).one()
    assert stored.status is DictionaryAdditionStatus.pending
    assert stored.proposal.citation is not None
    assert stored.proposal.citation.title == "Synthetic study"

    runs = db_session.scalars(
        select(AgentRun).where(AgentRun.proposal_id == stored.proposal_id)
    ).all()
    assert len(runs) == 4

    grown = db_session.scalars(
        select(Dictionary).where(Dictionary.source_proposal_id == stored.proposal_id)
    ).one()
    assert grown.last_updated_by == approver.id
