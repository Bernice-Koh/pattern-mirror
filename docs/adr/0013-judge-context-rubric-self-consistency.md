# 13. The Judge sees the document, answers a rubric, and confidence is sample agreement

- Status: Accepted
- Date: 2026-07-03
- Amends: ADR-0007, ADR-0008

## Context

An audit of the Judge stage (Stage 4, `engine/judge.py`) against the design spec and the
LLM-as-judge literature found three defects, all independent of any framework choice:

1. **The Judge never sees the document.** Its prompt lists each flag as
   `category | span | explanation` — the only "context" is the Contextual Pass's *own
   explanation* of why it flagged the span. The Judge is grading the generator's homework
   with the generator's answer key: its verdict is correlated with the very output it is
   meant to check (self-preference bias is causal, not incidental — Panickssery, Bowman &
   Feng 2024, arXiv:2404.13076). The spec's requirement that flags be judged "in context"
   is unmet.
2. **Confidence is a verbalized scalar.** ADR-0008 correctly treats it as uncalibrated,
   but a single stated number remains a feeling, not a measurement: Likert-style scalar
   judgments are unstable and lenient (Gu et al., arXiv:2411.15594), and nothing about the
   score is explainable after the fact — a problem in a product whose audit trail is a
   feature.
3. **Batch scoring with ordered verdicts.** All flags go in one call and verdicts come
   back positionally, exposing the stage to position bias (Wang et al., arXiv:2305.17926;
   Zheng et al., arXiv:2306.05685), cross-flag anchoring, and the brittle
   `JudgeVerdictCountError` failure when the count drifts.

Two constraints from ADR-0008 still hold and shape the fix. Anthropic's API exposes no
token logprobs, so confidence must be constructed, not read off. And the gold set is too
small to fit a calibration map (ADR-0011: measure before fit). The literature since has
been kinder to this position than expected: verbalized confidences from RLHF models
calibrate *better* than token probabilities (Tian et al., arXiv:2305.14975), and the
black-box/white-box confidence gap is small (Xiong et al., arXiv:2306.13063). ADR-0008's
architecture was right; its *signal* was the weak part. This ADR amends, not replaces.

## Decision

- **The Judge receives independent evidence: the document context, not the generator's
  explanation.** Each flag is presented with its span, category, and the surrounding
  document context (the containing sentence/paragraph window). The Contextual Pass's
  `explanation` is withheld — the Judge forms its own view from the source text, making it
  a genuine second opinion rather than a review of the generator's reasoning.
- **Rubric-decomposed scoring (CheckEval pattern, arXiv:2403.18771).** The
  `JudgeVerdict` schema's `confidence: float` is replaced by boolean/enum sub-questions
  mirroring the TAFEP GDOR test the Contextual Pass already applies (ADR-0010):
  does the span reference a protected characteristic; explicitly or as coded language; is
  a genuine occupational requirement plausible; is it stated objectively as a capability
  or outcome. Plus brief reasoning. **The model emits no confidence number at all.** A
  per-sample bias verdict is derived deterministically in code:
  `biased ⇔ references_characteristic AND NOT (gdor_plausible AND stated_objectively)`.
- **Self-consistency is the MVP default, promoted from ADR-0008's fallback.** The Judge
  runs N times per document (config, default 3, max 5), each sample with an independently
  shuffled flag order. Sampling diversity comes from inherent model non-determinism plus
  the shuffling (sampling parameters are being removed on Claude 4.6+).
  **Confidence = the fraction of samples whose derived verdict is `biased`** — a
  frequency, not a feeling (Wang et al., arXiv:2203.11171). Per-criterion agreement
  fractions are computed alongside and recorded in the `agent_runs` output for the
  calibration dashboard; no schema change to `flags`.
- **Verdicts are matched by flag id, not list position.** Each sample's schema keys its
  answers to an id assigned in the prompt (as the Contextual Pass already does), so a
  shuffled or short response degrades to a missing sample for that flag rather than
  corrupting every downstream verdict.
- **The Judge model stays Haiku 4.5.** The sampling budget is spent on N, not on tier:
  ~5 Haiku samples cost about one Sonnet call and buy a confidence distribution instead
  of one opinion. Rubric decomposition reduces each judgment to narrow questions a small
  model handles well, and Haiku remains a *different model* from the Sonnet generator —
  upgrading the Judge to Sonnet would create same-model judging, the worst
  self-preference configuration. Gold-set calibration runs go through the Batches API
  (50% off); the shared per-document prompt prefix is cached across samples.
- **The downstream contract is unchanged.** `JudgeScore.confidence` stays a
  `float | None` in [0, 1]; the calibration map, per-category config threshold, inclusive
  `>=` gate, and ECE/Brier measurement all stand as written in ADR-0008/0011. The
  aggregation function (samples → per-flag confidence) lives in `engine/calibration.py`
  as a pure, offline-testable function. ECE/Brier are re-measured on the gold set before
  and after the revamp.
- **Amendments.** ADR-0007: "the Judge emits confidence only" becomes "the Judge emits
  rubric answers only; confidence is derived in code" — the Adjudicator's ownership of
  span existence is untouched, and the semantic-groundedness gap ADR-0007 recorded is
  narrowed, since the Judge now checks the bias claim against the source text itself.
  ADR-0008: the verbalized scalar is retired and self-consistency moves from documented
  fallback to MVP default; everything else in ADR-0008 stands.

## Consequences

- **+** The Judge's evidence is independent of the generator's reasoning; the correlated-
  judge failure mode is structurally removed rather than prompted away.
- **+** Every score is audit-explainable: which criterion failed, and how consistently,
  is on the record per flag — auditability is a product requirement, not a nicety.
- **+** Confidence is an observed agreement frequency, the strongest confidence signal
  available without logprobs, and position bias is neutralized for free by the per-sample
  shuffle.
- **+** The derivation and aggregation are deterministic pure functions — unit-testable
  offline, per CONVENTIONS.
- **−** Judge cost and latency rise ~N× (default 3×). Accepted: Haiku is the cheapest
  agent in the pipeline, prompt caching discounts the shared prefix, and the Judge stage
  is not on the streaming-critical path ahead of flag persistence.
- **−** Confidence is quantized to multiples of 1/N (N=3 gives {0, ⅓, ⅔, 1}). Per-category
  thresholds must be chosen on that lattice; the inclusive `>=` boundary test matters
  more, not less.
- **−** Agreement fraction is *better-grounded*, not guaranteed-calibrated. The
  measure-before-fit discipline (ADR-0011) is unchanged; the before/after ECE/Brier delta
  on the gold set is the acceptance evidence for this ADR.
- **−** More moving parts: context-window extraction, a sample loop in the orchestrator's
  judge node, and the aggregation function.

## Alternatives considered

- **Keep the scalar and fit a calibration map** — rejected: fixes neither the correlated
  evidence nor the unexplainable score, and the gold set is too small to fit a map anyway
  (ADR-0011).
- **Upgrade the Judge to Sonnet 4.6** — rejected: judge = generator model is the worst
  self-preference configuration, against Anthropic's own grade-with-a-different-model
  guidance, and capability is not the bottleneck — evidence and aggregation are. A Sonnet
  *second opinion on the gold set only* (offline agreement measurement, Cohen's κ) remains
  a worthwhile add-on, not a production change.
- **One call per flag instead of a shuffled batch per sample** — rejected for MVP: it also
  kills anchoring but spends the extra calls buying isolation instead of an agreement
  distribution; shuffling across N samples addresses position bias while every marginal
  token buys confidence signal.
- **Full document as Judge context** — rejected for now: a span-level GDOR ruling needs
  the surrounding sentence/paragraph, and the full document invites the Judge to
  re-litigate other spans. Revisit if gold-set errors show context starvation.
- **DeepEval's G-Eval or DAG metric as the production judge** — rejected: on Anthropic
  models G-Eval silently degrades to a raw sampled score (no logprob weighting), and
  DeepEval's model wrapper parses JSON naively where our Instructor boundary retries on
  schema violations. The DAG metric's decision-tree idea is sound — this ADR adopts it
  natively. DeepEval remains a candidate for the offline eval harness only (separate
  decision, new dependency, ask-first).
- **Panel of judges across model families (PoLL)** — blocked: requires the multi-model
  gateway, which is a locked post-MVP decision. A Haiku-only panel is just
  self-consistency, which this ADR adopts.
