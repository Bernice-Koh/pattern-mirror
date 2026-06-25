# 9. Remove the severity signal

- Status: Accepted
- Date: 2026-06-26

## Context

`severity` (low/medium/high) was seeded on every dictionary entry, carried onto each flag,
and returned by `/analyze`. In practice nothing consumed it: the engine gates on the Judge's
**confidence**, not severity (ADR 0007/0008); the frontend declared a `Severity` type but
never rendered it; and for a contextual flag (#48) severity had no principled source — the
model would simply guess it.

Its only designed homes were the Dictionary Growth loop's Proposer ("proposes category,
severity, reasoning") and the HR review-queue (#72) — both unbuilt, and both expressible
without a severity field.

## Decision

- **Remove severity end to end.** Drop the `Severity` enum and `severity` PG type, the
  `dictionaries.severity` column (migration `0005_remove_severity`), and the field from
  `CandidateFlag`, the Contextual Pass output schema, `build_flag`, `FlagResponse`, and the
  frontend contract.
- **Confidence (the Judge) is the only per-flag strength signal.** Severity (a term-level
  notion) is not reintroduced on the flag.
- **Supersedes** §3's Proposer "proposes category, severity, reasoning" (now category and
  reasoning) and the `severity` mention in #19's acceptance criteria.

## Consequences

- **+** One fewer unverified, unrendered field to seed, carry, and (for contextual flags)
  invent; a simpler flag contract and lexicon schema.
- **+** Removes the awkward case of asking the LLM to rate a severity nothing checks.
- **−** If a term-level severity is wanted later (e.g. to weight the HR review-queue), it
  returns as a **dictionary** attribute, not a flag one — a new migration, not a revert.
- The merged seed migrations (`0001`–`0003`) still set the column transiently on a fresh
  build before `0005` drops it; released history is left unrewritten.

## Alternatives considered

- **Keep severity on the dictionary only, strip it from the flag/API** — the
  spec-preserving middle cut. Rejected by the owner: with no consumer and the growth
  loop/HR queue unbuilt, a partial keep is dead weight; reintroduce it as a dictionary
  attribute if and when a consumer exists.
