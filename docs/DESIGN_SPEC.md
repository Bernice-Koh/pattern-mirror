# The Pattern Mirror — Design Specification

> **Status: living product specification.** Originating from the Phase 4 design phase, this is
> the product source of truth referenced by [CLAUDE.md](../CLAUDE.md) and
> [CONVENTIONS.md](CONVENTIONS.md). It is maintained as a living document — edit it as the product
> evolves, with git history as the decision trail. Where an [ADR](adr/) conflicts with this
> document, **the ADR supersedes it**: ADRs remain the record for architecture decisions and their
> trade-offs, while this file describes the product itself.

---

## 1. Core Alignment & Positioning

**Business problem.** Unconscious bias in JDs, interview feedback, and promotion writeups carries real cost. No current tool surfaces it back to the manager who wrote it. The bias is unconscious — managers produce hundreds of these documents over their careers without realising the language patterns they fall into. Each document looks unobjectionable in isolation. Patterns only emerge across the full body of writing, invisible to the manager, to any single-document review, and to any current tool.

**Cost to the firm.** Qualified candidates filtered out before interview, narrowing the talent pipeline. Firm-level diversity targets missed despite training spend. Regulatory exposure to TAFEP guidance and SEA equivalents. Compliance training cost without measurable behaviour change.

**Why existing tools do not reach it.** Bias training teaches concepts but never shows the manager where their own writing violates those concepts. Organisation-wide diversity dashboards report outcomes at the firm level, not the writing producing them. Single-document bias checkers flag one word at a time, which the manager dismisses as false positives.

**Value proposition.** Pattern Mirror gives managers self-correcting evidence, and gives the firm measurable behaviour change.

- **Behaviour change at the source.** Managers see specific patterns in their own writing, with verifiable evidence. This is the leverage point that generic bias training does not reach.
- **Audit defensibility.** Every flag cites peer-reviewed research or TAFEP guidance. Every pattern is logged. HR Business Partners get aggregated visibility into firm-wide trends with no exposure to individual manager data.
- **ROI on existing training investment.** Bias training teaches concepts. Pattern Mirror shows where this manager's writing departs from those concepts, making the training operational.

**Design principles.**

- *Mirror, not judge.* Shows patterns to the manager, never penalises.
- *Private by architecture.* Individual writing visible only to the manager. HR sees aggregated trends only.
- *Non-blocking.* Every flag is dismissible. The tool never prevents a submission.
- *Evidence for every flag.* Each observation cites peer-reviewed academic research, region-specific guidance (e.g. TAFEP for SG), or the manager's own documented pattern.

**What this is NOT.** Not a chatbot — pattern detection is structural analysis, not conversation. Not another training module — the target user has already completed every bias training the bank offers. Not a hiring gate — the manager retains decision authority.

The tool is a **longitudinal behavioural intelligence tool** that tracks manager decisions over time, persists learning and patterns, expands coverage to promotions and internal mobility, and provides actionable, evidence-based insights rather than isolated flags.

---

## 2. Product Surfaces — Four Views, One Engine (Managers)

The Pattern Mirror exposes four surfaces to the manager, all backed by the same analysis engine and database. They are not four products; they are four views into the same body of work.

#### View 1 — JD Studio

The manager's writing surface for job descriptions. As they type or paste a JD, biased phrasing is underlined in real-time. The mental model is *Grammarly, but for hiring bias*. Every underline cites either TAFEP guidance or peer-reviewed research. Hover reveals the citation and explanation. The manager can accept, dismiss, or ignore.

JD Studio uses a **two-layer latency model**:

- **Layer 1 — Dictionary flags** · <100ms · live as the manager types. Deterministic, no LLM call. Like spellcheck.
- **Layer 2 — LLM contextual pass** · ~5–8s · streams in after a typing pause or save. Adds role-aware nuance and catches phrases the dictionary doesn't know.

The two layers feel like one experience to the manager — they see flags appear, some instantly, some a few seconds later, all dismissible with the same gesture.

#### View 2 — Feedback Checkpoint

The manager's writing surface for interview feedback. Before submitting feedback through UBS systems, the manager pastes their draft into Checkpoint. Two checks run in parallel:

- **Bias** in the language used (same engine as JD Studio).
- **Drift** — whether the feedback addresses the criteria stated in the original JD.

Example output:

**Original JD — Senior Associate role:** 5+ years Python · Strong SQL · Distributed systems experience · Ability to mentor juniors

**Interview feedback — Candidate A:** *"Candidate seemed nervous in the first 10 minutes. Strong technical background — handled the system design well. Not sure about culture fit; gave off a bit of a quiet vibe. Probably better suited for a back-office role."*

**DRIFT** — 3 of 4 stated criteria not addressed in feedback. **BIAS** — 4 observations outside JD scope: demeanour, vibe, alternative-role assignment.

The manager is not blocked. They see this before deciding whether to submit.

The candidate's resume is available within Checkpoint as a download link, for reference while reviewing the draft. See Section 5 for where resume files are stored.

#### View 3 — Pattern Dashboard

The longitudinal differentiator. The dashboard surfaces two layers of self-reflection content — patterns in the manager's writing, and patterns in the manager's decisions about flags. Both are gated by statistical significance (Fisher's exact test where applicable). Patterns that could plausibly be coincidence do not surface.

**Layer 1 — Pattern surfacing.** Patterns in the writing itself, across two modes:

Mode A — Per-role. One JD plus all feedback for that role. "You described 4 candidates as 'polished' — all 4 are women." "You described 5 candidates as 'sharp' — all 5 are men." p = 0.0008 · unlikely to be coincidence. Asymmetry is invisible in any single feedback note but obvious in aggregate within one hiring round.

Mode B — Across-time. The manager's full writing history. "Across your 32 feedback notes, 'cultural fit' appears 14 times — 13 about candidates whose backgrounds differ from your eventual hire's."

Each pattern is clickable — drill into the specific documents it came from.

**Layer 2 — Behavioural reflection.** Patterns in the manager's decisions about flags, drawn from the adoption metrics in Section 13. Surfaced per bias category and over time: "You dismiss gender-coded flags at 78%, age-coded flags at 31% — across 47 flags raised this quarter." "Your adoption rate has risen from 22% to 64% over the past six months, driven primarily by changes in gender-coded language."

This layer stays inside Mirror-not-Judge: it is the manager's own behavioural data, visible only to them, presented without editorialising. They draw the conclusion.

#### View 4 — Promotion Writeup

The manager's writing surface for promotion justifications. Triggered when the manager initiates "Evaluate for Promotion" against an employee. They enter their justification and supporting reasoning, and the tool runs two parallel checks:

Bias in the language used (same engine as JD Studio and Feedback Checkpoint). Drift — whether the writeup evidences the promotion rubric for the target level. Alongside the rubric coverage, the surface shows what the employee's historical peer feedback says for each criterion, as corroborating evidence: peers often supply the evidence a writeup omits.

Same non-blocking model as Feedback Checkpoint. The manager sees the analysis before deciding whether to submit. See Section 4 for architectural detail on the promotion workflow, including how the rubric and historical peer feedback are mocked in MVP.

The employee's resume / CV is available within the writeup view as a download link, for reference while drafting. See Section 5 for where resume files are stored.

---

## 3. The Analysis Engine

The engine is a bounded, named-step flow. Each stage is logged, each transition is traceable, and every flag has a verified span.

#### Five stages

**Stage 1 — Dictionary Service (Module).** spaCy lemma matching against the curated dictionary. Deterministic, no LLM call. Every hit cites TAFEP or peer-reviewed research. This is the Layer 1 latency tier.

**Stage 2 — LLM Contextual Pass (Agent).** One LLM call (Claude Sonnet 4.6 via Instructor for schema-enforced JSON). ~3–6s. Checks dictionary flags' validity by role context. Adds new flags the dictionary missed. Tags candidates as *general* (dictionary-eligible) versus *role-specific* (LLM-only).

**Stage 3 — Adjudicator (Module).** Deterministic code, no LLM call. Literal string-match every LLM-claimed span against the source. If the quote doesn't exist verbatim, drop the flag. This is the structural guarantee behind "every flag has evidence" — hallucinated spans cannot reach the manager.

**Stage 4 — LLM Judge (Agent).** Claude Haiku 4.5. Scores each surviving flag on two dimensions: **confidence** score (how strongly the bias claim holds). Flags below the confidence threshold do not progress further. The Judge's full reasoning and scores are persisted (Tier 2).

**Stage 5 — Recommendations Agent (Agent).** Sonnet 4.6 with a separate prompt and structured output schema. Generates 2–3 alternative phrasings for each high-confidence flag, anchored to citations. Only runs above the Judge's confidence threshold — see Section 7.

#### The drift-check stage (parallel to bias detection)

For Feedback Checkpoint and Promotion Workflow, a sixth concern runs alongside the five-stage bias pipeline: a **drift check** that compares the current writing against a reference document.

- **Feedback Checkpoint** drift check: interview feedback vs. the original JD criteria.
- **Promotion Workflow** drift check: promotion writeup vs. the promotion rubric for the target level.

Architecturally the same agent, swapped reference corpus. This is significant — promotion analysis does not require a new engine, just a different reference document into the existing drift stage. The employee's historical peer feedback is not a second drift corpus; it is surfaced as corroborating evidence against the same rubric (mocked in MVP), not run through the engine.

#### Why the structure matters

The bounded-flow design means the orchestrator (LangGraph) can log every transition, retry individual stages independently, and reconstruct exactly what happened on any flag.

---

## 4. The Dictionary — Foundation, Categories, and Growth

The dictionary is the engine's anchor to verifiable evidence. Without it, the tool is just another LLM bias checker — vulnerable to "the model said so" dismissals from sophisticated users.

#### Foundation: Singapore-scoped, TAFEP-grounded

Bias-language coding is region-specific. MVP anchors to SEA — e.g. Singapore with its TAFEP guidance, with academic backing where available.

| Category | Source | Example |
| ----- | ----- | ----- |
| Gender | Gaucher 2011 + TAFEP | "aggressive" → masculine-coded; ~25% drop in women applicants |
| Age | TAFEP + AARP | "digital native" → age-coded; excludes career-changers |
| Race / ethnicity | TAFEP | "Mandarin-speaking only" → indirect race exclusion in SG context |
| Nationality | TAFEP | "NSF-completed required" → excludes women, foreigners, PRs |
| Religion | TAFEP | Religion-tagged criteria not job-justified |
| Disability | TAFEP + academic | "able-bodied" without specific job-task justification |
| Family status | TAFEP | "married women preferred" / "mothers preferred" |

#### Region-pluggable by design

The engine is region-agnostic; the dictionary is region-specific. UK, US, EU, or other markets each load their own dictionary table at deployment. Same engine, different data — no rewrites to support additional jurisdictions. The PostgreSQL `dictionaries` table carries a region scope (`SG`, `MY`, `ID`, etc.) and the orchestrator selects the appropriate table at runtime.

#### Dictionary growth — multi-agent review

The dictionary is not static. As managers write across the firm, the LLM Contextual Pass (Stage 2) regularly proposes flags on phrases that aren't in the dictionary. **Most are role-specific** noise. A small fraction are genuine new bias-coded language that should become dictionary entries — and therefore become flaggable as fast deterministic dictionary hits in future writing, with proper citations.

The growth loop is where agentic AI does meaningful work in the product.

**Trigger.** The Contextual Pass repeatedly proposes the same phrase across multiple managers and documents, and that phrase is not in the dictionary.

**Four-agent review.** Once triggered, four agents independently evaluate the candidate:

1. **Proposer.** Argues for inclusion. Proposes category and reasoning.
2. **Skeptic.** Argues against. Is the phrase too narrow? Just standard business language? Is the evidence thin?
3. **Categorizer.** Tags scope. *General* (dictionary candidate, applies broadly) vs. *role-specific* (keep as LLM-only flag, do not add to dictionary).
4. **Citation.** Searches for academic or regulatory support. Absence of support means skip dictionary inclusion — the flag may still fire from the Contextual Pass, but it does not become a dictionary entry without citation.

**Decision rule.** 3 of 4 agents must agree to advance. The phrase enters a `pending_dictionary_additions` queue with all agent reasoning logged.

**Human-in-loop, monthly.** HR (or a designated reviewer) approves dictionary additions in bulk on a monthly cadence. This is not per-entry review — the agentic system has already filtered the queue. HR sees the pending phrase, the agent reasoning, the citation found, and approves, rejects, or defers. Approved entries become live dictionary rows with the citation attached.

**Full audit trail.** Every proposal, every agent argument, every HR decision is persisted (Tier 2 in Section 5). If a manager challenges a flag months later — "where did this rule come from?" — the chain back to original proposal, agent reasoning, citation, and HR approval is reconstructable.

---

## 5. Persistence Model

**Nothing in the system is transient.** Every flag, every manager decision, every agent output is persisted. The Pattern Aggregator and the effectiveness metrics depend on a complete event log — anything not stored cannot be analysed later.

Persisted data is organised in three tiers:

**Tier 1 — Must persist (drives core product value):**

- Every flag raised, with full provenance: which stage produced it, which dictionary entry or rule, structured rationale, judge confidence score
- Manager response to every flag: accepted / dismissed / ignored / edited-around
- The manager's final submitted text alongside the flagged version, so behavioural change is measurable against final outcomes rather than UI clicks alone
- Recommendations issued by the Recommendations Agent and which were taken

**Tier 2 — Persist for audit and debuggability:**

- Each agent's thought process and structured input/output
- Judge confidence and hallucination scores
- Which dictionary entries fired vs. which were added during the contextual LLM pass
- Approved and rejected items proposed for addition to the dictionary

**Tier 3 — Aggregate-only / derived:**

- Pattern Aggregator outputs (computed on demand, cached for the dashboard)
- Manager-level acceptance rate, bias category trends, drift over time

**Privacy frame.** Persistence is for the manager's own Pattern Dashboard and for audit. It does not change the privacy contract: individual writing remains visible only to the manager. HR continues to see aggregated trends only, never individual content.

**Storage medium.** Document text (JDs, interview feedback, promotion writeups), flags, dismissals, and all metadata are stored relationally in PostgreSQL — they are short-form, queryable, and read by the engine on every run. The only binary artefacts are candidate / employee **resume-CV files**, which the engine does not analyse as text; these are stored in blob storage (Azure Blob in production; a local-disk or Azurite stand-in in dev), with Postgres holding the blob reference and metadata. Resume files surface to the manager as download links in Feedback Checkpoint and Promotion Writeup. Broader blob usage — RAG over historical documents, the rejected-resume leaderboard (Section 11) — remains post-MVP.

---

## 6. Manager Behaviour & Override Handling

Managers retain full authority to override any flag. **The tool is non-blocking by design.**

**Interaction model: binary accept/dismiss.** A categorisation modal on every dismiss would kill seamlessness, and seamlessness is part of what makes the Mirror positioning credible. The interaction surface is therefore minimal — accept the recommendation, or X to dismiss. Both outcomes are logged.

**Implicit behaviour is the primary signal:**

- Edited the flagged span after the flag appeared → accepted, behaviourally
- Clicked X but the span remains in the final submission → active dismissal
- Clicked X and the span is gone from the final submission → dismissed-and-removed (likely adopted via rewrite)
- Never interacted with the flag → passive, signal weight depends on whether the span remains

**Pattern surfacing.** Override and dismissal patterns are surfaced in the Pattern Dashboard only after passing Fisher's exact significance testing — the same statistical threshold applied to flag patterns. Categories and rates are displayed; the dashboard does not editorialise. This preserves Mirror-not-Judge: the manager sees the evidence, draws the conclusion themselves.

---

## 7. Recommendations Agent

The current pipeline detects bias but does not propose alternatives. A dedicated Recommendations Agent sits in the orchestrator **after the Judge**, conditional on the Judge passing the flag above a confidence threshold.

**Why threshold-gated.** Running recommendations on every flag, including low-confidence ones, generates noisy suggestions and erodes trust quickly. Recommendations only fire on flags the Judge is confident about.

**Three operating principles:**

1. *Evidence-anchored alternatives, not prescriptions.* "Research on gendered language [citation] finds 'aggressive' is rated more negatively in feedback for women than men. Alternative framings used in peer-reviewed templates: 'direct', 'assertive', 'decisive'." The manager picks, or doesn't.
2. *Show, don't tell.* Surface 2–3 alternatives, never one "correct" answer. The moment there is one answer, the tool is judging.
3. *Recommendations are dismissible and logged.* Same interaction pattern as flags — dismissals and accepts are data.

**Implementation.** Reuse the same LLM as the Contextual Pass (Sonnet 4.6) with a separate prompt and structured output schema.

---

## 8. Promotion Workflow

**Trigger model.** Manager-initiated, not employee-initiated. The manager opens "Evaluate for Promotion," enters their justification and reasoning, and the tool runs analysis. Employee-triggered promotion requests are out of scope.

**Two analytical passes:**

1. The existing five-stage engine against the **general bias dictionary** — gender-coded, racial-coded, age-coded language, all SEA-scoped categories already in MVP scope.
2. A **drift / coverage check** against the **promotion rubric** for the target level — which rubric criteria the writeup evidences.

**Architecturally this is not a new agent.** It is the existing drift-check stage (already used in Feedback Checkpoint to compare interview feedback against JD criteria) with a swapped reference document — the promotion rubric instead of the JD. Same pattern, different reference corpus. The rubric is the promotion analogue of a role's JD criteria: manager-entered/seeded now, AI-drafted-with-confirm later.

**Historical peer feedback (corroborating evidence).** UBS has an existing feedback system where employees can request feedback from anyone working with them — colleagues, managers, etc. — collected as three free-text fields stored in a relational database. The Promotion Writeup surfaces this alongside the rubric coverage as *corroborating evidence*: for each rubric criterion, whether peers evidence it — so a manager sees when peers already supply the evidence a writeup omits. This is not a second engine pass; the peer corroboration is **mocked as synthetic data** in MVP (a fact about the employee, not the writeup). Integration with the actual UBS feedback system, and inferring corroboration live, are post-MVP.

The Recommendations Agent runs on promotion-workflow flags the same way it does for JDs and feedback — same threshold, same principles.

---

## 9. Hiring Workflow Considerations

**External hiring.** Background checks remain with external vendors. The tool represents background-check status as a Boolean checkmark; it does not perform or analyse the check itself.

**Internal hiring and promotions.** Same engine, same Recommendations Agent, same general bias dictionary. Internal moves trigger the promotion workflow described in Section 4, with the drift check against historical peer feedback.

**Bias detection on hiring writeups** (external) covers manager justifications and shortlisting rationale, scanned by the five-stage engine and recommended on by the Recommendations Agent above confidence threshold.

---

## 10. Architecture & System Design

### Terminology

Consistent technical naming across diagrams and documentation:

- All intelligent components → Agents (Contextual Pass, Judge, Recommendations, and the four Dictionary Growth agents — Proposer, Skeptic, Categorizer, Citation)
- All data-interacting and deterministic components → Modules (Dictionary Service, Adjudicator, Pattern Aggregator)

### Diagram updates

- Managers represented as an **actor icon**, not a system or orchestrator block. Reinforces "the manager is the user, the tool is the mirror."
- Rename "trigger analysis" → "**trigger content analysis**" for specificity.

### Model strategy

Production path uses Sonnet 4.6 (Contextual Pass, Recommendations) and Haiku 4.5 (Judge). A **side-by-side comparison evaluation** against DeepSeek (and optionally one other model) is run on a fixed eval set to report cost-per-flag and agreement rate. This evaluation does not affect the MVP production path — model swap is not in MVP scope. The Multi-Model Gateway remains a future-vision component.

---

## 11. HR System Scope

**Minimal MVP scope: light-touch, read-only viewer.** HR sees the Aggregated Trends Dashboard, served by SQL queries via the FastAPI layer. HR is represented as an **actor**, not a passive system, but their actionable surface in MVP is minimal — they observe firm-level patterns; they do not see individual manager content.

**Report generation.** HR can generate aggregate reports across three dimensions:

**Effectiveness —** adoption rate over time, by flag category, by document type. Tells leadership whether the tool is driving behaviour change.

**Calibration —** gold-set agreement over time, dismiss-and-kept rate by category. Tells leadership whether the tool's flags are trusted and where they're being rejected.

**Dictionary health —** proposal volume, agent agreement rate, citation coverage, HR approval throughput. Tells leadership whether the dictionary is growing in a controlled way.

**Full-vision: rejected-resume leaderboard.** When HR is filtering resumes — manually or via existing automated systems — the tool scans rejected resumes against the JD criteria and surfaces a leaderboard of "rejected but fits JD" candidates. Redis as a leaderboard cache is appropriate.

This feature carries a risk: existing HR tools may already do something similar. The differentiating angle is that the LLM pipeline provides a **per-candidate "why" summary** — the structured rationale for why a rejected candidate fits the JD criteria — which most existing tools do not. This is the selling angle if challenged.

The rejected-resume leaderboard is **not confirmed to be within MVP**. High effort and tight timeline.

---

## 12. Semantic Flag Tracking: Lemma Fingerprints and Re-Check

State management is **backend-resident**, not frontend-transient.

Reasoning: the agentic flow runs on the backend and must know what has been dismissed before it streams new flags or makes redundant Sonnet calls; frontend state breaks on refresh, multi-tab, and session resumption; the dismissal data is also the input to the Pattern Aggregator, so storing it in two places creates desync risk.

### The duplicate-flag problem

Dictionary scans run near-real-time. The agentic flow runs after 5 seconds of user idle. Without de-duplication, the same word can be flagged repeatedly — first by the dictionary, then again by Sonnet — even after the manager dismisses it once. This pollutes the manager's experience and corrupts the dismissal data feeding the Pattern Aggregator.

### Flag signature

A flag's identity is `(document_id, rule_id, normalised_span_text, sentence_fingerprint)`.

- **Document-scoped, not manager-scoped.** Once dismissed within a document, stays dismissed for that document. Across documents, every new document is a fresh check. This preserves the longitudinal pattern story — if the manager keeps using "aggressive" across many JDs, the Pattern Dashboard surfaces it, even though each individual JD only nags them once.
- **Span normalisation handles trivial variations.** Lowercase, strip punctuation, lemmatise. "aggressive", "Aggressive", "aggressive!" all match.

### Sentence fingerprint (lemma bag hash)

For the sentence containing each flagged span, extract the lemma bag with spaCy (already in use for the dictionary stage) and hash it. The hash is the context fingerprint.

- "aggressive leader" → `{aggressive, leader}` → hash A
- "aggressive leader." (added period) → `{aggressive, leader}` → hash A — no re-trigger ✓
- "Aggressive leader" (capitalisation) → `{aggressive, leader}` → hash A — no re-trigger ✓
- "aggressive go-getter" → `{aggressive, go-getter}` → hash B — re-trigger ✓
- "aggressive, dynamic leader" → `{aggressive, dynamic, leader}` → hash C — re-trigger ✓

A dismissal means "I have considered this concern in this context." When the context is unchanged, the previous judgement still applies. When the context shifts, the manager re-judges.

### Suppression logic

When the engine produces a candidate flag, it computes the signature and looks up dismissals matching `(doc_id, rule_id, normalised_span)`:

- No match → new flag, surface.
- Match with same `sentence_fingerprint` → genuinely the same flag, suppress.
- Match with different `sentence_fingerprint` → context shifted, surface as a new flag.

**Log everything, suppress only in UI.** Every flag the engine generates is persisted, including suppressed ones, with a `suppressed=true|false` boolean and a reference to the dismissal that caused the suppression. The frontend renders only un-suppressed flags. This way:

- The manager sees each issue once
- The Pattern Aggregator can still observe that a word fired N times in a document even when the manager saw it once
- Suppression logic can be revised later without losing data

### Edge case: sentence boundary instability

spaCy sentence segmentation can occasionally shift on punctuation edits, changing the fingerprint for trivial reasons. If this surfaces in testing, swap from "containing sentence" to a **fixed N-token window around the span** (e.g., 8 tokens each side). Less semantically clean, more stable under editing. Decision made empirically once we see real edit traces.

### Edge case: deleted span

Manager dismisses, then deletes the span entirely during a rewrite. The dismissal row remains; it matches nothing in the new text. This is fine for storage. The Pattern Aggregator distinguishes "dismissed-and-kept" from "dismissed-and-removed" by joining dismissals against the final submitted text at submission time.

### Manual re-check button

For the case where the manager has done a major rewrite and wants a clean pass:

```
POST /documents/{doc_id}/recheck
  → Mark all flag_dismissals.active = false for this document
  → Trigger fresh engine run on current document text
  → Stream all flags (including previously suppressed) via SSE
```

---

## 13. Adoption Metrics

The tool's effectiveness is measured at the **outcome level** — what ends up in the final submitted document — not at the interaction level.

A manager who rewrites their own version that avoids the flag is arguably a *better* outcome than one who clicks accept and uses our exact wording: they internalised the feedback rather than complying with it. Both count as adoption.

### 5 behavioural states per flag

**Clear adoption (tool worked):**

1. **Explicit accept** — clicked accept, text now matches the suggestion
2. **Edited around it** — didn't accept, didn't dismiss, but the flagged span is gone or changed in the final submission, and the edit happened after the flag was displayed
3. **Dismissed and removed** — clicked X, but the text is gone from the final submission

**Clear rejection (tool didn't change behaviour):**

4. **Dismissed and kept** — clicked X, text remains in the final submission
5. **Ignored and kept** — never interacted with the flag, text remains

### Primary headline metric

**Adoption Rate = (States 1 + 2 + 3) / total flags raised.**

Phrased for UBS audiences: *"In X% of cases where the tool flagged bias-coded language, the language was removed or revised in the final submission."* This avoids over-claiming causal attribution while reporting the meaningful business outcome.

### Effectiveness vs. calibration are separate metrics

A high dismissal rate could mean either *managers resist the tool* or *the tool's flags are noisy*. The Pattern Aggregator must not conflate them. Three independent metrics:

- **Dismiss-and-kept rate** → manager-driven rejection
- **Adoption rate** (states 1+2+3) → tool-driven behaviour change
- **Agreement with held-out gold set** → tool calibration

The evaluation dashboard reports all three. No composite "success score."

### "Edited around it" is the product-improvement signal

If managers consistently *don't* click accept but *do* change the flagged text, the detection pipeline is working but the recommendation phrasing isn't landing. That's a Recommendations Agent problem, not a flag-detection problem. Tracking State 2 separately lets us iterate on the Recommendations Agent prompt without questioning the underlying flag pipeline.

### Aggregation levels

Adoption is aggregated and surfaced at multiple levels:

- **By flag category** — which bias categories (gender-coded, age-coded, etc.) land vs. don't
- **By manager** — feeds the individual Pattern Dashboard, framed as their own improvement trend
- **By document type** — JD vs. feedback vs. promotion writeup, surfaces where the tool is most useful
- **Over time** — week-over-week, quarter-over-quarter longitudinal story

Aggregate-across-managers is the number shown to HR and leadership. Per-manager is the number shown only to the individual manager, never to HR.
