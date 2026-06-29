"""Gold-set calibration metrics: precision/recall per stage, agreement, ECE, Brier (#23, ADR-0008).

Pure functions over predictions and gold labels — no database, no engine, no LLM — so they run
deterministically in CI. The live measurement (``jobs.calibrate``) runs the real engine over the
gold set, turns its flags into ``Prediction`` rows and the labels into ``LabelKey`` rows, and calls
``evaluate``. A flag's identity here is ``(category, normalised_span, source_stage)``; matching is
exact on that key, so the caller normalises both sides the same way the engine does.
"""

from dataclasses import dataclass

from pattern_mirror.models.enums import BiasCategory, FlagSourceStage


@dataclass(frozen=True)
class LabelKey:
    """A gold flag's identity: what the engine should have produced, and from which stage."""

    category: BiasCategory
    normalised_span: str
    source_stage: FlagSourceStage


@dataclass(frozen=True)
class Prediction:
    """One flag the engine produced. ``confidence`` is the Judge's raw score, None when unscored."""

    category: BiasCategory
    normalised_span: str
    source_stage: FlagSourceStage
    confidence: float | None = None

    @property
    def key(self) -> LabelKey:
        return LabelKey(self.category, self.normalised_span, self.source_stage)


@dataclass(frozen=True)
class StageMetrics:
    """Precision/recall for one stage, from the true/false positive and false negative counts."""

    stage: FlagSourceStage
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float | None:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else None

    @property
    def recall(self) -> float | None:
        actual = self.true_positives + self.false_negatives
        return self.true_positives / actual if actual else None


@dataclass(frozen=True)
class CalibrationReport:
    """The whole measurement: per-stage precision/recall, overall agreement, and calibration."""

    per_stage: dict[FlagSourceStage, StageMetrics]
    agreement: float | None
    ece: float | None
    brier: float | None
    scored_count: int


def _stage_metrics(
    stage: FlagSourceStage, predicted: set[LabelKey], gold: set[LabelKey]
) -> StageMetrics:
    return StageMetrics(
        stage=stage,
        true_positives=len(predicted & gold),
        false_positives=len(predicted - gold),
        false_negatives=len(gold - predicted),
    )


def precision_recall_per_stage(
    predictions: list[Prediction], labels: list[LabelKey]
) -> dict[FlagSourceStage, StageMetrics]:
    """Per-stage precision/recall, matching prediction keys against gold-label keys.

    Both sides are reduced to key sets, so a span flagged twice counts once; a stage with
    neither prediction nor label is omitted.
    """
    metrics: dict[FlagSourceStage, StageMetrics] = {}
    for stage in FlagSourceStage:
        predicted = {p.key for p in predictions if p.source_stage is stage}
        gold = {label for label in labels if label.source_stage is stage}
        if predicted or gold:
            metrics[stage] = _stage_metrics(stage, predicted, gold)
    return metrics


def agreement_rate(predictions: list[Prediction], labels: list[LabelKey]) -> float | None:
    """Agreement as the Jaccard overlap of predicted and gold flags; None when both are empty."""
    predicted = {p.key for p in predictions}
    gold = set(labels)
    union = predicted | gold
    return len(predicted & gold) / len(union) if union else None


def _confidence_outcomes(
    predictions: list[Prediction], labels: list[LabelKey]
) -> tuple[list[float], list[int]]:
    """Confidence and hit (1 if the scored flag matches a gold label) for each scored prediction."""
    gold = set(labels)
    confidences: list[float] = []
    outcomes: list[int] = []
    for prediction in predictions:
        if prediction.confidence is not None:
            confidences.append(prediction.confidence)
            outcomes.append(1 if prediction.key in gold else 0)
    return confidences, outcomes


def expected_calibration_error(
    confidences: list[float], outcomes: list[int], n_bins: int = 10
) -> float | None:
    """Binned gap between stated confidence and actual hit rate (ADR-0008); None when no samples.

    Lower is better — 0 means a bucket's stated confidence equals how often those flags were right.
    """
    if len(confidences) != len(outcomes):
        raise ValueError("confidences and outcomes must be the same length")
    total = len(confidences)
    if total == 0:
        return None
    bin_hits: list[list[int]] = [[] for _ in range(n_bins)]
    bin_confs: list[list[float]] = [[] for _ in range(n_bins)]
    for confidence, outcome in zip(confidences, outcomes, strict=True):
        index = min(int(confidence * n_bins), n_bins - 1)
        bin_hits[index].append(outcome)
        bin_confs[index].append(confidence)
    error = 0.0
    for hits, confs in zip(bin_hits, bin_confs, strict=True):
        if hits:
            accuracy = sum(hits) / len(hits)
            mean_confidence = sum(confs) / len(confs)
            error += (len(hits) / total) * abs(accuracy - mean_confidence)
    return error


def brier_score(confidences: list[float], outcomes: list[int]) -> float | None:
    """Mean squared error between confidence and outcome; None when no samples. Lower is better."""
    if len(confidences) != len(outcomes):
        raise ValueError("confidences and outcomes must be the same length")
    if not confidences:
        return None
    return sum(
        (confidence - outcome) ** 2
        for confidence, outcome in zip(confidences, outcomes, strict=True)
    ) / len(confidences)


def evaluate(
    predictions: list[Prediction], labels: list[LabelKey], n_bins: int = 10
) -> CalibrationReport:
    """Assemble the full report from one engine run's predictions against the gold labels."""
    confidences, outcomes = _confidence_outcomes(predictions, labels)
    return CalibrationReport(
        per_stage=precision_recall_per_stage(predictions, labels),
        agreement=agreement_rate(predictions, labels),
        ece=expected_calibration_error(confidences, outcomes, n_bins),
        brier=brier_score(confidences, outcomes),
        scored_count=len(confidences),
    )
