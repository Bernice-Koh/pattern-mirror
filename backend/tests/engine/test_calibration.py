"""Confidence calibration, rubric derivation, and the Judge's threshold gate (ADR-0008/0013)."""

import pytest

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.calibration import (
    agreement_fraction,
    calibrate_confidence,
    derive_bias_verdict,
    passes_threshold,
    threshold_for,
)
from pattern_mirror.models.enums import BiasCategory


def _settings(
    *, threshold: float = 0.7, overrides: dict[BiasCategory, float] | None = None
) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://x:y@localhost/db",
        judge_confidence_threshold=threshold,
        judge_confidence_threshold_overrides=overrides or {},
    )


@pytest.mark.parametrize(
    ("references", "gdor", "objective", "expected"),
    [
        (True, False, False, True),  # references a characteristic, no GDOR defence
        (True, True, False, True),  # GDOR claimed but not stated objectively
        (True, False, True, True),  # objective but no GDOR — still an identity reference
        (True, True, True, False),  # genuine requirement, stated objectively
        (False, False, False, False),  # no protected characteristic referenced
    ],
)
def test_derive_bias_verdict_truth_table(
    references: bool, gdor: bool, objective: bool, expected: bool
) -> None:
    assert (
        derive_bias_verdict(
            references_characteristic=references,
            gdor_plausible=gdor,
            stated_objectively=objective,
        )
        is expected
    )


def test_agreement_fraction_counts_true_votes() -> None:
    assert agreement_fraction([True, True, True]) == 1.0
    assert agreement_fraction([True, False, False]) == pytest.approx(1 / 3)
    assert agreement_fraction([False, False]) == 0.0


def test_agreement_fraction_of_no_votes_is_zero() -> None:
    assert agreement_fraction([]) == 0.0


def test_calibrate_confidence_is_the_identity_map() -> None:
    # ADR-0008: the map starts as identity until one is fitted on the gold set (#23).
    for raw in (0.0, 0.3, 0.7, 1.0):
        assert calibrate_confidence(raw) == raw


def test_threshold_boundary_is_inclusive() -> None:
    assert passes_threshold(0.7, 0.7) is True
    assert passes_threshold(0.70001, 0.7) is True
    assert passes_threshold(0.69999, 0.7) is False


def test_threshold_for_uses_the_global_default_without_an_override() -> None:
    settings = _settings(threshold=0.7)

    assert threshold_for(BiasCategory.gender, settings) == 0.7


def test_threshold_for_prefers_a_category_override() -> None:
    settings = _settings(threshold=0.7, overrides={BiasCategory.age: 0.5})

    assert threshold_for(BiasCategory.age, settings) == 0.5
    assert threshold_for(BiasCategory.gender, settings) == 0.7
