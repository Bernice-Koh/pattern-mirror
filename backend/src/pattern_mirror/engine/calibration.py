"""Confidence calibration, the Judge's rubric derivation, and the threshold gate.

The Judge no longer emits a confidence; it answers a GDOR rubric per sample (ADR-0013).
``derive_bias_verdict`` turns one sample's answers into a boolean, and ``agreement_fraction``
turns the samples' votes into a confidence — the self-consistency signal. The gate then runs
on the *calibrated* score against a config threshold (ADR-0008). The calibration map starts as
the identity and is replaced by a fitted map only if the gold set shows material
miscalibration (#23) — because the gate reads ``calibrate(raw)``, that swap is one line here.
"""

from pattern_mirror.core.config import Settings
from pattern_mirror.models.enums import BiasCategory


def derive_bias_verdict(
    *, references_characteristic: bool, gdor_plausible: bool, stated_objectively: bool
) -> bool:
    """Whether one rubric sample judges a flag biased (ADR-0013).

    A phrase is biased when it references a protected characteristic and is not a genuine
    occupational requirement stated objectively.
    """
    return references_characteristic and not (gdor_plausible and stated_objectively)


def agreement_fraction(votes: list[bool]) -> float:
    """The fraction of ``True`` votes; the self-consistency confidence. 0.0 for no votes."""
    return sum(votes) / len(votes) if votes else 0.0


def calibrate_confidence(raw: float) -> float:
    """Map a raw confidence to a calibrated one. Identity until a map is fitted."""
    return raw


def threshold_for(category: BiasCategory, settings: Settings) -> float:
    """The gate threshold for a category: its override if set, else the global default."""
    return settings.judge_confidence_threshold_overrides.get(
        category, settings.judge_confidence_threshold
    )


def passes_threshold(calibrated: float, threshold: float) -> bool:
    """Whether a calibrated confidence clears the gate. Boundary is inclusive: ``>=`` passes."""
    return calibrated >= threshold
