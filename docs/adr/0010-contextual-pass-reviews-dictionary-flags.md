# 10. The Contextual Pass reviews the dictionary flags; only unacceptable surfaces

- Status: Accepted
- Date: 2026-06-28

## Context

Design spec §12 names the duplicate-flag problem: the dictionary (Layer 1) and the
Contextual Pass (Layer 2) can flag the same or an overlapping span — "young" and "young
rockstar" — so one concern surfaces as two cards and the dismissal signal feeding the Pattern
Aggregator is corrupted (issue #81). The original framing was to **de-duplicate after** both
layers run.

But the dictionary is literal and context-blind: it matches lemmas and cannot tell genuine
bias from a Genuine and Determining Occupational Requirement (GDOR) or a plain false positive.
The TAFEP guidance (`docs/references/tafep_example_excerpts.md`) already defines three verdicts
— `acceptable`, `acceptable_with_justification`, `unacceptable` — and the schema was scaffolded
for them: the `FlagVerdict` enum and the (until now unused) `flags.verdict` column already
exist.

## Decision

- **Prevent the duplicate at the source, not after.** The Contextual Pass receives the
  dictionary flags and does two things: (1) rules each against the GDOR test, returning a
  verdict and reasoning; (2) adds only the bias the keyword list missed, instructed not to
  re-flag or overlap a keyword span.
- **A deterministic Verdict node applies the rulings.** The append-only candidate channel
  keeps the dictionary flags out of the Pass's reach, so the Pass emits its rulings on a side
  channel and the Verdict node (after the Adjudicator, before the Judge) attaches them and
  partitions the flags.
- **Only `unacceptable` flags surface.** `acceptable` (a false positive in context) and
  `acceptable_with_justification` are persisted with `suppressed=true` and their verdict —
  logged for the Pattern Aggregator, not shown to the manager (log everything, suppress in
  UI). On an overlap the dictionary hit is the surfaced anchor.
- **No post-hoc overlap or de-duplication logic exists.**
- **Supersedes** design spec §12's "de-duplicate after" framing.

## Consequences

- **+** Duplicates cannot arise: the Pass never emits an overlapping flag, so one concern is
  one card.
- **+** The `verdict` column is now populated; false positives and GDOR-justified references
  are captured for the Pattern Aggregator and HR calibration without nagging the manager.
- **+** The Judge spends no tokens on flags the Pass already cleared (the Verdict node runs
  before it).
- **−** Prevention leans on the model following the prompt; a stray overlapping new flag is
  possible. Accepted: the cost is one duplicate card, not a correctness failure, and the
  deterministic alternative was rejected by the owner as the wrong design.
- **−** `acceptable_with_justification` references are not shown (owner decision); they live
  only in the log. A later "flag for review" surface would read the persisted verdict — no
  re-run needed.
- **−** `verdict` is not exposed on the surfaced API or frontend: only `unacceptable` surfaces,
  so it would be a constant field (the ADR 0009 principle — no field nothing consumes).

## Alternatives considered

- **Post-hoc de-duplication (the issue's original framing)** — a deterministic Module drops the
  overlap loser after both layers run. Rejected by the owner: it cleans up a mess instead of
  preventing it, and still spends LLM tokens generating the duplicate.
- **Surface `acceptable_with_justification` for review** — rejected by the owner for a cleaner
  panel; the data is logged either way.
