# pattern-mirror

A longitudinal bias-pattern analysis tool for managers — real-time bias flagging in hiring and promotion writing, drift checks against stated criteria, and statistically-gated pattern surfacing across a manager's full body of writing.

Built for the UBS Tomorrow's Talent Programme 2026, Technology Track.

**Status:** in development — MVP targeted at the programme's final showcase (July 2026)

---

## The problem

Unconscious bias in job descriptions, interview feedback, and promotion writeups carries real cost: qualified candidates filtered out before interview, diversity targets missed despite training spend, and regulatory exposure under TAFEP guidance and SEA equivalents.

The bias is unconscious. A manager produces hundreds of these documents over a career, and each one looks unobjectionable in isolation. The patterns only emerge across the full body of writing — invisible to the manager, to any single-document review, and to any current tool.

Existing approaches don't reach it:

- Bias training teaches concepts, but never shows a manager where their own writing departs from them.
- Firm-level diversity dashboards report outcomes, not the writing producing them.
- Single-document bias checkers flag one word at a time and get dismissed as false positives.

Pattern Mirror closes that gap: it surfaces patterns in a manager's own writing, with evidence, so they can decide what to do.

## What it does

Four views for the manager, all backed by one analysis engine and one database:

| View | Purpose |
|---|---|
| **JD Studio** | Real-time bias flagging while writing a job description — dictionary flags in <100ms, an LLM contextual pass streaming in after a typing pause. Every flag cites TAFEP guidance or peer-reviewed research. |
| **Feedback Checkpoint** | Pre-submission check on interview feedback: bias in the language, plus drift against the criteria stated in the original JD. |
| **Pattern Dashboard** | Longitudinal self-reflection — patterns across the manager's writing (per-role and across-time) and patterns in their own decisions about flags. Only patterns passing Fisher's exact significance testing surface. |
| **Promotion Writeup** | Pre-submission check on promotion justifications: bias in the language, plus drift against historical peer feedback for that employee. |

HR Business Partners get a separate read-only portal showing aggregated firm-level trends — never individual manager content.

### Design principles

- **Mirror, not judge.** The tool shows patterns to the manager; it never penalises.
- **Private by architecture.** Individual writing is visible only to the manager; HR sees aggregates only — enforced by the data model, not by policy.
- **Non-blocking.** Every flag is dismissible. The tool never prevents a submission.
- **Evidence for every flag.** Each observation cites peer-reviewed research, region-specific guidance, or the manager's own documented pattern.

## How it works

The engine is a bounded, five-stage flow orchestrated as an explicit state graph. Every stage is logged, every transition traceable, every flag span-verified:

1. **Dictionary Service** — deterministic spaCy lemma matching against a curated, citation-backed dictionary. No LLM call.
2. **LLM Contextual Pass** — one schema-enforced LLM call adding role-aware nuance and flags the dictionary missed.
3. **Adjudicator** — deterministic span verification: any LLM-claimed quote that doesn't exist verbatim in the source is dropped. Hallucinated flags cannot reach the manager.
4. **LLM Judge** — scores each surviving flag on confidence and hallucination risk; low-confidence flags terminate here.
5. **Recommendations Agent** — generates 2–3 evidence-anchored alternative phrasings, only for flags above the Judge's confidence threshold.

A parallel **drift check** (same engine, swapped reference corpus) compares feedback against JD criteria, or promotion writeups against historical peer feedback.

The dictionary is Singapore-scoped and TAFEP-grounded for MVP, and region-pluggable by design — the engine is region-agnostic, the dictionary is data. It grows through a four-agent review loop (Proposer, Skeptic, Categorizer, Citation) with monthly human-in-the-loop approval.

Full architecture, sequence diagrams, and decision records live in [docs/](docs/).

## Tech stack

- **Frontend:** React + TypeScript, Vite, Tailwind, TipTap (editor surfaces), Recharts (dashboards)
- **Backend:** Python 3.12, FastAPI, SSE streaming
- **AI / agents:** Anthropic Claude (Sonnet 4.6 analysis, Haiku 4.5 judge), Instructor for structured outputs, LangGraph orchestration, spaCy for lemma matching
- **Data:** PostgreSQL 16 (metadata, flags, patterns, dictionaries, audit logs) + Azure Blob Storage (document blobs); SQLAlchemy 2.x + Alembic
- **Statistics:** scipy (Fisher's exact test gating pattern surfacing)
- **Deploy:** Docker Compose locally; Azure Container Apps as the production target

## Roadmap

- **MVP (programme scope):** the four manager views, the five-stage engine, drift checks, the SG/TAFEP dictionary with the agentic growth loop, the HR aggregated-trends portal, and a seeded demo dataset.
- **Post-MVP:** real UBS feedback-system integration (MVP mocks peer feedback as synthetic data), RAG over Azure Blob for historical retrieval, multi-model gateway, additional region dictionaries (UK / US / EU / MY / ID / TH / PH / VN), ATS/HRIS connectors, rejected-resume leaderboard, full Azure production hardening.

## Repository layout

```
backend/    Python/FastAPI — engine, agents, API, jobs
frontend/   React/TS — manager portal and HR portal
docs/       Architecture, sequence diagrams, ADRs, conventions
deploy/     docker-compose and deployment glue
```

## Documentation

- [docs/CONVENTIONS.md](docs/CONVENTIONS.md) — engineering workflow, testing, git, project management
- [docs/CODE_STYLE.md](docs/CODE_STYLE.md) — language-level style rules for Python and TypeScript
- [docs/adr/](docs/adr/) — architecture decision records
- [CLAUDE.md](CLAUDE.md) — collaboration rules for AI-assisted development on this repo

---

Built by Bernice Koh as part of the UBS Tomorrow's Talent Programme 2026, with guidance from a UBS engineering buddy and mentor.
