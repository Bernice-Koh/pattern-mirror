# 12. Four agents review a growth candidate; 3-of-4 with a citation advances it

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
- **The gate is 3-of-4 in favour.** A vote in favour is: Proposer supports, Skeptic's verdict
  supports, Categorizer scopes `general`, Citation found support.
- **A found citation is a hard requirement.** A phrase advances only when a citation was found
  *and* at least three Agents favour it — a missing citation blocks dictionary inclusion even
  when the other three agree. This keeps the "every dictionary entry cites a verifiable source"
  promise (ADR 0006) intact for grown entries.
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
- **+** Dissent is structural — the Skeptic exists to fail weak candidates, and the citation
  requirement stops uncited phrases from ever reaching the dictionary.
- **+** The mixed model tiering spends Sonnet tokens only where reasoning quality matters; the
  cheap classification runs on Haiku. Volume is low (a monthly batch), so cost is modest either
  way.
- **−** The Citation agent recalls sources from model knowledge and can hallucinate one. Accepted
  for the MVP: real web-search/tool-use grounding is post-MVP, and the monthly human-in-the-loop
  approval (#90) is the backstop — no phrase becomes a live rule without HR sign-off.
- **−** Four calls per candidate is more expensive than one classifier. Accepted: the trigger
  (#88) gates volume to recurring phrases, and the audit defensibility is the point of the
  feature.
- **−** The 3-of-4 count treats all four votes as equal weight. Accepted as the spec's rule; if
  it proves too lax or strict, the threshold is a one-line change (`GROWTH_AGREEMENT_THRESHOLD`).

## Alternatives considered

- **A single classifier Agent** — one call labels the candidate. Rejected: no dissent, no scoped
  judgement, no citation, and a black-box decision that fails the audit-defensibility goal.
- **Unanimous (4-of-4) gate** — rejected as too strict; a lone Skeptic dissent would kill genuine
  candidates, and the citation-required override already guards the one dimension that must hold.
- **Citation as a soft vote** (counts toward the three but doesn't block) — rejected: it would let
  an uncited phrase advance on the strength of the other three, breaking ADR 0006 for grown rows.
