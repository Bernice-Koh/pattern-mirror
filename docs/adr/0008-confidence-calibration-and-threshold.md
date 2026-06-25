# 8. Confidence scoring without logprobs: verbalized score, gold-set calibration, config threshold

- Status: Accepted
- Date: 2026-06-25

## Context

Threshold gating (§3 Stage 4; §7 Recommendations) needs a per-flag confidence score. The
standard way to derive model confidence — token logprobs — is **not exposed by Anthropic's
API**, so it is unavailable on Haiku 4.5 (the Judge model). A raw verbalized confidence from
an LLM is well known to be poorly calibrated, so thresholding it directly gives a meaningless
cutoff.

## Decision

- **Verbalized confidence.** The Judge emits a confidence as a structured Pydantic field in
  [0, 1], treated as **uncalibrated**.
- **Calibrated threshold.** Gating operates on a **calibrated** score from a post-hoc
  calibration map (start with isotonic or Platt) fit from raw to calibrated on the held-out
  **gold set** (§14 / #23). Report **ECE + Brier** on the calibration dashboard (§11).
- **One threshold, in config.** Defined once in configuration (not a code constant),
  **per-bias-category-capable**, with an explicit **`>=` (inclusive)** boundary: a flag whose
  calibrated confidence equals the threshold passes. It gates both the Judge (low-confidence
  flags terminate) and Recommendations (only above-threshold flags get rewrites). A boundary
  test is required.
- **Post-MVP fallback:** self-consistency (sample N, confidence = agreement fraction) if
  single-call calibration proves too noisy — documented, not the MVP default.

## Consequences

- **+** Honest about LLM confidence: calibration is measured (ECE/Brier), not assumed.
- **+** A single source of truth for the threshold gates two stages consistently; per-category
  capability allows tuning where categories behave differently.
- **−** The threshold is only meaningful once the gold set exists and the calibration map is
  fit (#23); before that, the raw score is used with a documented caveat.
- **−** Verbalized score plus post-hoc calibration is weaker than true logprob confidence;
  accepted as the best available under the API constraint.

## Alternatives considered

- **Logprob-based confidence** — unavailable: Anthropic exposes no token logprobs.
- **Raw verbalized score as the gate** — rejected: poorly calibrated; the cutoff would be
  arbitrary.
- **Self-consistency (N-sample agreement) as the MVP default** — rejected for MVP: N× cost
  and latency on every flag; kept as a documented fallback.
- **Threshold as a code constant** — rejected: it must be tunable per category and per
  environment without a code change.
