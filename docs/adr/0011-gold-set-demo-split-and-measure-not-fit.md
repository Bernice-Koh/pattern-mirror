# 11. Gold set / demo dataset split; calibration is measured before it is fitted

- Status: Accepted
- Date: 2026-06-30

## Context

#23 asks one labelled dataset to do two jobs: seed the demo surfaces and measure engine
calibration. CONVENTIONS treats the gold set as doubling as demo seed, but the two pull in
opposite directions. The Pattern Dashboard (#66) only surfaces patterns that clear Fisher's
exact, which needs **volume** — a single clean gender split needs ~9 uses across a ~24-subject
history to reach p < 0.001. The calibration gold set must stay **small and hand-verified**: a
raw→calibrated confidence map (ADR-0008) fitted to a handful of points overfits, and verbalized
LLM confidence is systematically overconfident, so a bad map is worse than none.

A second tension: ECE/Brier are only meaningful against the real model's confidences, but CI
must stay deterministic and offline (CONVENTIONS: tests never hit the live API).

## Decision

- **Two fixtures, not one.** `seed_data/demo_dataset.json` is the high-volume writing-pattern
  seed (subjects + feedback engineered to clear Fisher's); `seed_data/gold_set.json` is the
  small labelled answer key for calibration. They are authored and loaded separately.
- **Measure now, fit later.** This issue computes precision/recall per stage, agreement, ECE,
  and Brier. It does **not** fit a calibration map. `engine.calibration.calibrate_confidence`
  stays the identity; the gate reads `calibrate(raw)`, so introducing a fitted map later is a
  one-line change, decided empirically from the measured ECE/Brier.
- **Pure metrics in CI; live run on demand.** `services/calibration.py` holds the metric maths
  as pure functions, unit-tested deterministically. `jobs/calibrate.py` makes the real Anthropic
  calls, runs the engine over the gold set on scratch rows it rolls back, and reports — never in
  CI.
- **Significance verified standalone.** Until the Pattern Aggregator (#66) exists, a test
  computes the same word-by-gender Fisher's tables the Aggregator will and asserts the showcase
  patterns clear p < 0.001, enough patterns clear p < 0.05, and a control word does not.

## Consequences

- **+** Each fixture is sized for its own job; neither compromises the other.
- **+** Calibration numbers are honest (real model) yet CI stays offline and fast.
- **+** The "run the Aggregator surfaces N patterns" criterion is verified now, by the same
  statistics #66 will use, without waiting on #66.
- **−** Two fixtures to keep coherent rather than one; the gold set is not seeded into the demo
  database (it is eval data), so the demo and the calibration corpus are distinct.
- **−** Calibration is a manual step with an API cost; its output is not yet surfaced (the HR
  calibration dashboard is #71).

## Alternatives considered

- **One combined dataset** — the literal CONVENTIONS reading. Rejected: the size needed for
  Fisher's makes a hand-verified gold set unwieldy, and a large gold set tempts premature map
  fitting.
- **Deterministic calibration from canned outputs** — fully reproducible, but the numbers would
  grade fixtures we wrote, not the model; indefensible if questioned. Rejected.
- **Fit a Platt/isotonic map now** — rejected per ADR-0008: too few points; fit only if the
  measured ECE/Brier show material miscalibration.
