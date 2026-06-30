"""Firm-wide HR aggregates: adoption breakdowns, dismiss-and-kept, and small-cell suppression."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagInteraction
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    DocumentStatus,
    FlagInteractionKind,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.calibration import CalibrationReport, StageMetrics
from pattern_mirror.services.calibration_runs import record_run
from pattern_mirror.services.hr_aggregates import (
    calibration_report,
    dictionary_health_report,
    effectiveness_report,
)

pytestmark = pytest.mark.db

_MARCH = datetime(2026, 3, 1, tzinfo=UTC)


def _manager(db_session: Session, index: int) -> User:
    user = User(
        external_user_id=f"hr-agg-manager-{index}",
        legal_name=f"Manager {index}",
        email=f"hr.agg.{index}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _submitted_flag(
    db_session: Session,
    owner: User,
    *,
    category: BiasCategory,
    span: str,
    kind: FlagInteractionKind,
    present_in_final: bool,
    doc_type: DocType = DocType.feedback,
    submitted_at: datetime = _MARCH,
) -> None:
    final_text = f"a notably {span} contributor" if present_in_final else "a balanced contributor"
    document = Document(
        owner_id=owner.id,
        doc_type=doc_type,
        status=DocumentStatus.submitted,
        submitted_content=final_text,
        submitted_at=submitted_at,
    )
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.submit,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    db_session.flush()
    flag = Flag(
        document_id=document.id,
        analysis_run_id=run.id,
        source_stage=FlagSourceStage.dictionary,
        category=category,
        scope=FlagScope.general,
        raw_span=span,
        normalised_span=span,
        sentence_fingerprint="f" * 64,
        rationale={},
    )
    db_session.add(flag)
    db_session.flush()
    db_session.add(FlagInteraction(flag_id=flag.id, kind=kind))
    db_session.flush()


def test_effectiveness_aggregates_adoption_across_managers(db_session: Session) -> None:
    # Three managers, each one accepted (adopted) and one dismissed-and-kept (rejected) gender flag.
    for index in range(3):
        manager = _manager(db_session, index)
        _submitted_flag(
            db_session,
            manager,
            category=BiasCategory.gender,
            span=f"accepted{index}",
            kind=FlagInteractionKind.accept,
            present_in_final=False,
        )
        _submitted_flag(
            db_session,
            manager,
            category=BiasCategory.gender,
            span=f"kept{index}",
            kind=FlagInteractionKind.dismiss,
            present_in_final=True,
        )

    report = effectiveness_report(db_session, min_cell_size=3)

    by_category = {cell.category: cell for cell in report.adoption_by_category}
    assert by_category[BiasCategory.gender].adopted_count == 3
    assert by_category[BiasCategory.gender].total_count == 6
    assert by_category[BiasCategory.gender].adoption_rate == 0.5
    assert [cell.period for cell in report.adoption_over_time] == ["2026-03"]
    assert report.adoption_over_time[0].total_count == 6
    by_doc_type = {cell.doc_type: cell for cell in report.adoption_by_doc_type}
    assert by_doc_type[DocType.feedback].total_count == 6


def test_cells_below_the_minimum_manager_count_are_suppressed(db_session: Session) -> None:
    for index in range(2):
        _submitted_flag(
            db_session,
            _manager(db_session, index),
            category=BiasCategory.gender,
            span=f"accepted{index}",
            kind=FlagInteractionKind.accept,
            present_in_final=False,
        )

    suppressed = effectiveness_report(db_session, min_cell_size=3)
    visible = effectiveness_report(db_session, min_cell_size=2)

    assert suppressed.adoption_by_category == ()
    assert suppressed.adoption_over_time == ()
    assert {cell.category for cell in visible.adoption_by_category} == {BiasCategory.gender}


def test_calibration_reports_dismiss_and_kept_rate_by_category(db_session: Session) -> None:
    for index in range(3):
        manager = _manager(db_session, index)
        _submitted_flag(
            db_session,
            manager,
            category=BiasCategory.gender,
            span=f"kept{index}",
            kind=FlagInteractionKind.dismiss,
            present_in_final=True,
        )
        _submitted_flag(
            db_session,
            manager,
            category=BiasCategory.gender,
            span=f"removed{index}",
            kind=FlagInteractionKind.dismiss,
            present_in_final=False,
        )

    report = calibration_report(db_session, min_cell_size=3)

    by_category = {row.category: row for row in report.dismissed_and_kept_by_category}
    assert by_category[BiasCategory.gender].dismissed_and_kept_count == 3
    assert by_category[BiasCategory.gender].total_count == 6
    assert by_category[BiasCategory.gender].dismissed_and_kept_rate == 0.5


def test_calibration_includes_the_persisted_gold_set_trend(db_session: Session) -> None:
    record_run(
        db_session,
        CalibrationReport(
            per_stage={
                FlagSourceStage.dictionary: StageMetrics(FlagSourceStage.dictionary, 9, 1, 0)
            },
            agreement=0.9,
            ece=0.08,
            brier=0.04,
            scored_count=10,
        ),
    )

    report = calibration_report(db_session, min_cell_size=3)

    assert len(report.gold_set_trend) == 1
    assert report.gold_set_trend[0].agreement == 0.9


def test_empty_database_returns_empty_reports(db_session: Session) -> None:
    effectiveness = effectiveness_report(db_session, min_cell_size=3)
    calibration = calibration_report(db_session, min_cell_size=3)
    health = dictionary_health_report(db_session)

    assert effectiveness == effectiveness_report(db_session, min_cell_size=3)
    assert effectiveness.adoption_over_time == ()
    assert effectiveness.adoption_by_category == ()
    assert effectiveness.adoption_by_doc_type == ()
    assert calibration.gold_set_trend == ()
    assert calibration.dismissed_and_kept_by_category == ()
    assert health.proposal_volume is None
    assert health.agent_agreement_rate is None
