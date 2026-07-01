# 12. Four agents review a growth candidate; two hard gates plus a debater vote advance it

- Status: Accepted
- Date: 2026-07-01

## Context

The dictionary is not static (design spec §3). The Contextual Pass regularly proposes flags on
phrases that aren't catalogued; most are role-specific noise, a small fraction are genuine new
bias-coded language that should become fast deterministic dictionary hits. Something has to
decide which recurring phrases earn a dictionary entry, and the decision has to be defensible
months later — "where did this rule come from?" is an audit question, not a preference.

A single LLM classifier could label each candidate, but one model's yes/no is a black box: no
dissent, no scoped judgement, no source. The design spec names a four-agent review instead, and
this ADR settles the shapes, the gate, and the model choices #89 needs to build it.

## Decision

- **Four independent Agents evaluate each triggered phrase**, each a single schema-enforced
  Anthropic call (Instructor), each logged to `agent_runs` against its `dictionary_proposals`
  row:
  - **Proposer** — argues for inclusion and picks the single best-fit bias category.
  - **Skeptic** — argues against, then gives an honest verdict (standard business language? too
    narrow? thin evidence?).
  - **Categorizer** — scopes the phrase `general` (dictionary candidate) vs `role_specific`
    (stays a context-only flag, never a dictionary row).
  - **Citation** — searches for academic/regulatory support and returns the source, or reports
    none found.
- **The gate is two hard eligibility gates plus a debater vote.** A phrase advances only when
  **both** the Citation agent found support **and** the Categorizer scoped it `general`, and at
  least one of the two debaters (Proposer or Skeptic) supports inclusion.
- **The Citation and Categorizer verdicts are vetoes, not mere votes.** A missing citation breaks
  the "every dictionary entry cites a verifiable source" promise (ADR 0006); a `role_specific`
  scope means "keep as a context-only flag, never a dictionary entry" (design spec §3). Either
  one blocks inclusion regardless of the other votes — so the two eligibility agents decide
  whether the phrase is a dictionary candidate at all, and the Proposer/Skeptic pair is the
  genuine debate over it. A `votes_in_favour` tally across all four is still logged for the audit
  trail, but it does not itself decide the gate.
- **Every proposal is logged, advancing or not.** A `dictionary_proposals` row and four
  `agent_runs` are written for every candidate, so a rejection is as reconstructable as an
  advance. A `pending_dictionary_additions` row exists iff the phrase advanced.
- **Per-agent models:** Proposer, Skeptic, and Citation run on **Sonnet 4.6** (argumentation and
  citation recall need the stronger model); the Categorizer runs on **Haiku 4.5** (a narrow
  scope classification). Models live in config, tunable without a code change.
- **The four agents are a batch flow, not part of the analysis engine graph.** They run over a
  trigger's candidates (#88), not per-document, so they live in `engine/growth/` with a
  persistence service in `services/dictionary_growth.py`, outside the LangGraph pipeline.

## Consequences

- **+** The decision carries its own reasoning: four arguments plus a citation, all logged, so
  HR's monthly review (#90) reads a case rather than a label, and #91 can reconstruct the chain.
- **+** Dissent is structural — the Skeptic exists to fail weak candidates, and the two
  eligibility gates stop uncited *or* role-specific phrases from ever reaching the dictionary.
- **+** The mixed model tiering spends Sonnet tokens only where reasoning quality matters; the
  cheap classification runs on Haiku. Volume is low (a monthly batch), so cost is modest either
  way.
- **−** The Citation agent recalls sources from model knowledge and can hallucinate one. Accepted
  for the MVP: real web-search/tool-use grounding is post-MVP, and the monthly human-in-the-loop
  approval (#90) is the backstop — no phrase becomes a live rule without HR sign-off.
- **−** Four calls per candidate is more expensive than one classifier. Accepted: the trigger
  (#88) gates volume to recurring phrases, and the audit defensibility is the point of the
  feature.
- **−** The gate departs from the design spec's literal "3-of-4 agreement" wording, which would
  let a `role_specific` phrase advance on the other three votes. That was judged a defect: it
  contradicts the Categorizer's own "do not add to dictionary" semantics, so the two eligibility
  agents were promoted to vetoes. The spec and issue #89 were updated to match.

## Alternatives considered

- **A single classifier Agent** — one call labels the candidate. Rejected: no dissent, no scoped
  judgement, no citation, and a black-box decision that fails the audit-defensibility goal.
- **Unanimous (4-of-4) gate** — rejected as too strict; a lone Skeptic dissent would kill genuine
  candidates, whereas the eligibility gates already guard the two dimensions that must hold.
- **The spec's literal 3-of-4 count** (all four equal, citation the only veto) — rejected: it
  lets a `role_specific` phrase advance on Proposer + Skeptic + Citation, contradicting the
  Categorizer's purpose. Promoting `general` to a veto alongside citation fixes this.
- **Citation/scope as soft votes** (count toward agreement but don't block) — rejected: either
  would let an uncited or role-specific phrase advance on the others' strength, breaking ADR 0006
  or leaking a context-only flag into the dictionary.

## Addendum — the trigger's recurrence bar (#88, 2026-07-02)

This ADR calls the trigger (#88) the volume gate that makes four calls per candidate affordable.
Settling that bar: it is an **occurrence floor, not a cross-manager count**. Recurrence is an
*economic* filter, not a correctness one — the four agents here already judge the two things a
recurrence count proxies for (the Categorizer judges generality; the Proposer/Skeptic/Citation
trio judges merit), so requiring a phrase to appear across *multiple managers* before review just
duplicates that judgement and adds false negatives (a genuine general term one well-read manager
used). The one scale-independent reason to require *any* recurrence is that the trigger dedupes —
each phrase is reviewed once — so firing on the first sighting would spend that single review on
n=1 evidence with no revisit. A floor of two documents removes that risk at negligible cost.
Defaults are therefore `growth_recurrence_min_managers=1`, `growth_recurrence_min_documents=2`;
both stay in config so a cross-manager bar can be re-imposed at production volume.
