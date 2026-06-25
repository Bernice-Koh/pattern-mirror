# 7. The Adjudicator owns span existence; the Judge scores confidence only

- Status: Accepted
- Date: 2026-06-25

## Context

§3 Stage 4 has the Judge score each surviving flag on **two** dimensions: confidence and
"hallucination risk (independent check against the source text)." But §3 Stage 3 — the
Adjudicator — already guarantees **deterministically** that every surviving flag's claimed
span exists verbatim in the source (literal string match; hallucinated spans are dropped
before the Judge, see #20 and #45). A probabilistic Judge "hallucination risk" therefore
re-checks, less reliably, a property that is already a hard guarantee.

## Decision

- **The Adjudicator is the single, deterministic gate for span existence**, and resolves
  offsets for offset-less contextual spans (#45).
- **The Judge emits confidence only.** The hallucination-risk score is removed from the
  Judge's output schema and from persistence.
- **Supersedes** §3 Stage 4's two-dimension wording and §5 Tier 2's "Judge confidence and
  hallucination scores" (now confidence only).

## Consequences

- **+** No redundant probabilistic re-check of a deterministic guarantee; a simpler Judge
  schema and a single quantity to threshold.
- **+** Clear separation of concerns: existence is deterministic (a Module), strength-of-claim
  is probabilistic (an Agent).
- **−** A **semantic groundedness** check on the bias *rationale* — distinct from span
  presence (does the cited reasoning actually apply to this span?) — is not performed in MVP.
  Recorded as a possible post-MVP addition.

## Alternatives considered

- **Keep both Judge dimensions** — rejected: hallucination risk duplicates the Adjudicator's
  deterministic guarantee and muddies which gate is authoritative for span existence.
