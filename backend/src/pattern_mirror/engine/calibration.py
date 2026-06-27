"""Confidence calibration and the Judge's threshold gate (ADR-0008).

The Judge emits an uncalibrated verbalized confidence; the gate runs on a *calibrated* score
against a config threshold. The calibration map starts as the identity and is replaced by a
fitted map only if the gold set shows material miscalibration (#23) — because the gate reads
``calibrate(raw)``, that swap is one line here, not a refactor.
"""

from pattern_mirror.core.config import Settings
from pattern_mirror.models.enums import BiasCategory


def calibrate_confidence(raw: float) -> float:
    """Map a raw verbalized confidence to a calibrated one. Identity until a map is fitted."""
    return raw


def threshold_for(category: BiasCategory, settings: Settings) -> float:
    """The gate threshold for a category: its override if set, else the global default."""
    return settings.judge_confidence_threshold_overrides.get(
        category, settings.judge_confidence_threshold
    )


def passes_threshold(calibrated: float, threshold: float) -> bool:
    """Whether a calibrated confidence clears the gate. Boundary is inclusive: ``>=`` passes."""
    return calibrated >= threshold
