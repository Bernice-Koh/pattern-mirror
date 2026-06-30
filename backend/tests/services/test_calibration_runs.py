"""record_run persists a calibration measurement and calibration_history returns it in order."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.models.calibration import CalibrationRun
from pattern_mirror.models.enums import FlagSourceStage
from pattern_mirror.services.calibration import CalibrationReport, StageMetrics
from pattern_mirror.services.calibration_runs import calibration_history, record_run

pytestmark = pytest.mark.db


def _report() -> CalibrationReport:
    return CalibrationReport(
        per_stage={
            FlagSourceStage.dictionary: StageMetrics(
                stage=FlagSourceStage.dictionary,
                true_positives=8,
                false_positives=2,
                false_negatives=1,
            )
        },
        agreement=0.8,
        ece=0.1,
        brier=0.05,
        scored_count=10,
    )


def test_record_run_persists_the_metrics_and_per_stage_shape(db_session: Session) -> None:
    run = record_run(db_session, _report())

    assert run.agreement == 0.8
    assert run.ece == 0.1
    assert run.brier == 0.05
    assert run.scored_count == 10
    assert run.per_stage["dictionary"]["precision"] == 0.8
    assert run.per_stage["dictionary"]["true_positives"] == 8


def test_calibration_history_returns_runs_oldest_first(db_session: Session) -> None:
    # created_at is set explicitly: now() is constant within a transaction, so it cannot order rows.
    older = CalibrationRun(
        scored_count=1, per_stage={}, created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = CalibrationRun(
        scored_count=2, per_stage={}, created_at=datetime(2026, 6, 1, tzinfo=UTC)
    )
    db_session.add_all([newer, older])
    db_session.flush()

    history = calibration_history(db_session)

    assert [run.scored_count for run in history] == [1, 2]
