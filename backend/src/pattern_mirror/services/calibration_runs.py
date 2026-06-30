"""Persist and read gold-set calibration measurements (#23, #70).

The only module that touches the ``CalibrationRun`` model: ``jobs.calibrate`` calls ``record_run``
after measuring the engine, and the HR aggregates read the series with ``calibration_history`` to
chart calibration over time (§11). ``per_stage_metrics`` is the one place the per-stage shape is
defined, shared with the job's structured log.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.models.calibration import CalibrationRun
from pattern_mirror.services.calibration import CalibrationReport


def per_stage_metrics(report: CalibrationReport) -> dict[str, dict[str, Any]]:
    """The per-stage precision/recall and confusion counts, keyed by stage value."""
    return {
        stage.value: {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
        }
        for stage, metrics in report.per_stage.items()
    }


def record_run(session: Session, report: CalibrationReport) -> CalibrationRun:
    """Persist one calibration measurement; the caller owns the transaction commit."""
    run = CalibrationRun(
        agreement=report.agreement,
        ece=report.ece,
        brier=report.brier,
        scored_count=report.scored_count,
        per_stage=per_stage_metrics(report),
    )
    session.add(run)
    session.flush()
    return run


def calibration_history(session: Session) -> list[CalibrationRun]:
    """Every recorded calibration run, oldest first — the time series for the HR dashboard."""
    statement = select(CalibrationRun).order_by(CalibrationRun.created_at, CalibrationRun.id)
    return list(session.scalars(statement))
