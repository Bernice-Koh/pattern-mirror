"""Calibration metrics compute precision/recall, agreement, ECE, and Brier from known inputs."""

import math

import pytest

from pattern_mirror.models.enums import BiasCategory, FlagSourceStage
from pattern_mirror.services.calibration import (
    LabelKey,
    Prediction,
    agreement_rate,
    brier_score,
    evaluate,
    expected_calibration_error,
    precision_recall_per_stage,
)


def _label(span: str, stage: FlagSourceStage = FlagSourceStage.dictionary) -> LabelKey:
    return LabelKey(BiasCategory.age, span, stage)


def _pred(
    span: str,
    stage: FlagSourceStage = FlagSourceStage.dictionary,
    confidence: float | None = None,
) -> Prediction:
    return Prediction(BiasCategory.age, span, stage, confidence)


def test_precision_recall_counts_per_stage() -> None:
    predictions = [
        _pred("young"),  # true positive
        _pred("foreigner"),  # false positive (no gold label)
        _pred("rockstar", FlagSourceStage.contextual),  # true positive, other stage
    ]
    labels = [
        _label("young"),
        _label("mature"),  # false negative (missed)
        _label("rockstar", FlagSourceStage.contextual),
    ]

    metrics = precision_recall_per_stage(predictions, labels)

    dictionary = metrics[FlagSourceStage.dictionary]
    assert (dictionary.true_positives, dictionary.false_positives, dictionary.false_negatives) == (
        1,
        1,
        1,
    )
    assert dictionary.precision == 0.5
    assert dictionary.recall == 0.5
    contextual = metrics[FlagSourceStage.contextual]
    assert contextual.precision == 1.0
    assert contextual.recall == 1.0


def test_precision_recall_undefined_when_no_predictions() -> None:
    metrics = precision_recall_per_stage([], [_label("young")])
    assert metrics[FlagSourceStage.dictionary].precision is None
    assert metrics[FlagSourceStage.dictionary].recall == 0.0


def test_category_mismatch_is_not_a_match() -> None:
    predictions = [Prediction(BiasCategory.gender, "young", FlagSourceStage.dictionary)]
    labels = [LabelKey(BiasCategory.age, "young", FlagSourceStage.dictionary)]
    dictionary = precision_recall_per_stage(predictions, labels)[FlagSourceStage.dictionary]
    assert dictionary.true_positives == 0


def test_agreement_is_jaccard_overlap() -> None:
    predictions = [_pred("young"), _pred("foreigner")]
    labels = [_label("young"), _label("mature")]
    # intersection {young} = 1, union {young, foreigner, mature} = 3
    assert agreement_rate(predictions, labels) == pytest.approx(1 / 3)


def test_agreement_is_none_when_empty() -> None:
    assert agreement_rate([], []) is None


def test_ece_is_zero_for_perfectly_calibrated_input() -> None:
    # Two bins, each with hit rate equal to its stated confidence.
    confidences = [0.2, 0.2, 0.2, 0.2, 0.8, 0.8, 0.8, 0.8]
    outcomes = [0, 0, 0, 1, 1, 1, 1, 0]  # 0.25 ~ 0.2 region, 0.75 ~ 0.8 region
    error = expected_calibration_error(confidences, outcomes, n_bins=10)
    assert error is not None
    assert error < 0.06


def test_ece_grows_with_overconfidence() -> None:
    # Stated 0.9 but never right -> large gap.
    error = expected_calibration_error([0.9, 0.9, 0.9], [0, 0, 0], n_bins=10)
    assert error == pytest.approx(0.9)


def test_ece_none_without_samples() -> None:
    assert expected_calibration_error([], []) is None


def test_brier_rewards_confident_and_correct() -> None:
    assert brier_score([1.0, 0.0], [1, 0]) == pytest.approx(0.0)
    assert brier_score([0.5, 0.5], [1, 0]) == pytest.approx(0.25)


def test_metric_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        expected_calibration_error([0.5], [1, 0])
    with pytest.raises(ValueError, match="same length"):
        brier_score([0.5], [1, 0])


def test_evaluate_assembles_the_full_report() -> None:
    predictions = [
        _pred("young"),
        _pred("rockstar", FlagSourceStage.contextual, confidence=0.9),
        _pred("ninja", FlagSourceStage.contextual, confidence=0.8),  # false positive
    ]
    labels = [_label("young"), _label("rockstar", FlagSourceStage.contextual)]

    report = evaluate(predictions, labels)

    assert report.scored_count == 2
    assert report.per_stage[FlagSourceStage.dictionary].precision == 1.0
    assert report.agreement == pytest.approx(2 / 3)  # {young, rockstar} / {young, rockstar, ninja}
    assert report.ece is not None and report.brier is not None
    assert not math.isnan(report.brier)
