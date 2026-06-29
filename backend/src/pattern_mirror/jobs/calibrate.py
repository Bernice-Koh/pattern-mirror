"""Measure the live engine against the gold set and report calibration (#23, ADR-0008).

Run on demand (``python -m pattern_mirror.jobs.calibrate``); it makes real Anthropic calls, so it
is never part of CI. For each gold document it creates scratch ``users``/``documents``/
``analysis_runs`` rows the engine's audit writes need, invokes the real graph, turns the produced
flags into predictions, then rolls the scratch rows back — calibration measures the engine, it does
not pollute demo data. Predictions and labels are pooled across the gold set and scored once. The
calibration map stays the identity (``engine.calibration``); this job decides whether fitting one is
warranted, it does not fit it.
"""

import hashlib
from typing import Any

import structlog
from sqlalchemy.orm import Session

from pattern_mirror.core.config import get_settings
from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, build_instructor_client
from pattern_mirror.engine.orchestrator import build_default_graph
from pattern_mirror.engine.state import initial_state
from pattern_mirror.engine.suppression import normalised_span_of
from pattern_mirror.jobs.gold_set import GoldDocument, GoldSet, load_gold_set
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.enums import AnalysisTrigger, FlagSourceStage
from pattern_mirror.models.identity import User
from pattern_mirror.services.calibration import (
    CalibrationReport,
    LabelKey,
    Prediction,
    evaluate,
)

_REGION_CODE = "SG"
_log = structlog.get_logger("pattern_mirror.jobs.calibrate")


def _predictions_for_document(
    session: Session,
    gold_doc: GoldDocument,
    *,
    contextual_client: StructuredCompletionClient,
    judge_client: StructuredCompletionClient,
) -> list[Prediction]:
    """Run the live engine over one gold document and return its flags as predictions.

    Creates the scratch rows the engine's ``agent_runs`` writes reference (a throwaway user, the
    document, and the run); the caller rolls them back. Recommendations are skipped — they do not
    affect detection or confidence, so paying for them would buy no metric.
    """
    user = User(
        external_user_id="calibration-scratch",
        legal_name="Calibration",
        email="calibration@example.invalid",
    )
    session.add(user)
    session.flush()
    document = Document(owner_id=user.id, doc_type=gold_doc.doc_type, content=gold_doc.content)
    session.add(document)
    session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.submit,
        content_hash=hashlib.sha256(gold_doc.content.encode("utf-8")).hexdigest(),
    )
    session.add(run)
    session.flush()

    graph = build_default_graph(
        session,
        contextual_client=contextual_client,
        judge_client=judge_client,
        recommendations_client=None,
    )
    final = graph.invoke(
        initial_state(
            analysis_run_id=run.id,
            document_id=document.id,
            document_text=gold_doc.content,
            doc_type=gold_doc.doc_type,
            region_code=_REGION_CODE,
        )
    )

    predictions = [
        Prediction(flag.category, normalised_span_of(flag), FlagSourceStage.dictionary)
        for flag in final["candidate_flags"]
        if flag.source_stage is FlagSourceStage.dictionary
    ]
    predictions += [
        Prediction(
            score.flag.category,
            normalised_span_of(score.flag),
            FlagSourceStage.contextual,
            score.confidence,
        )
        for score in final["judge_scores"]
        if score.flag.source_stage is FlagSourceStage.contextual
    ]
    return predictions


def _gold_labels(gold_doc: GoldDocument) -> list[LabelKey]:
    """The document's should-surface labels as match keys, normalised like the engine's spans."""
    return [
        LabelKey(label.category, lemma_key(label.raw_span), label.source_stage)
        for label in gold_doc.labels
        if label.should_surface
    ]


def run_calibration(
    session: Session,
    gold_set: GoldSet,
    *,
    contextual_client: StructuredCompletionClient,
    judge_client: StructuredCompletionClient,
) -> CalibrationReport:
    """Score the live engine over the whole gold set, rolling back each document's scratch rows."""
    predictions: list[Prediction] = []
    labels: list[LabelKey] = []
    for gold_doc in gold_set.documents:
        predictions += _predictions_for_document(
            session,
            gold_doc,
            contextual_client=contextual_client,
            judge_client=judge_client,
        )
        labels += _gold_labels(gold_doc)
        session.rollback()
    return evaluate(predictions, labels)


def report_fields(report: CalibrationReport) -> dict[str, Any]:
    """Flatten a report into structured log fields (and the shape #71's dashboard will consume)."""
    return {
        "agreement": report.agreement,
        "ece": report.ece,
        "brier": report.brier,
        "scored_count": report.scored_count,
        "stages": {
            stage.value: {
                "precision": metrics.precision,
                "recall": metrics.recall,
                "true_positives": metrics.true_positives,
                "false_positives": metrics.false_positives,
                "false_negatives": metrics.false_negatives,
            }
            for stage, metrics in report.per_stage.items()
        },
    }


def main() -> None:
    """Run calibration against the configured database and live API, logging the report."""
    settings = get_settings()
    client = build_instructor_client(settings)
    if client is None:
        raise SystemExit("ANTHROPIC_API_KEY is required to calibrate against the live engine")

    session = get_sessionmaker()()
    try:
        report = run_calibration(
            session,
            load_gold_set(),
            contextual_client=client,
            judge_client=client,
        )
    finally:
        session.rollback()
        session.close()
    _log.info("calibration.report", **report_fields(report))


if __name__ == "__main__":  # pragma: no cover
    main()
