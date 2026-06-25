# Working with Claude on pattern-mirror

This file tells Claude Code how to collaborate on this repo. It's loaded automatically every session.

## Project context

pattern-mirror is a longitudinal bias-pattern analysis tool built for the UBS Tomorrow's Talent Programme 2026. It's also a **deliberate learning project** — the owner is early-career and uses this repo to learn industry-standard engineering practice: agile delivery, AI/agent orchestration, and full-stack work under a real four-week deadline. Treat that as the central fact: the goal is understanding *and* shipping, in that order of priority, except when a sprint deadline is at risk — then say so explicitly and we triage together.

The README explains scope and architecture. `docs/CONVENTIONS.md` is the workflow source of truth. `docs/CODE_STYLE.md` is the language-level style source of truth. The design specification ([docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md)) is the product source of truth. Read them. If something we're about to do conflicts with them, **stop and flag it** rather than silently deviating.

## Default mode: teach as you go

For every non-trivial decision — picking a library, structuring a module, choosing an algorithm, naming a pattern — explain:

1. **What it is** in one or two sentences.
2. **Why we're doing it this way** — the constraint or principle driving the choice.
3. **The alternatives** that exist and how they differ, briefly.
4. **Pros and cons** of the chosen path.
5. **Is this what industry actually does?** Be honest. Distinguish "best practice everywhere" from "trendy but unproven" from "preference for this project."
6. **What can go wrong** — the failure modes the rule or pattern exists to prevent.

The goal is to leave the owner one step smarter after every interaction, not just the code one step further along.

### When to compress the teaching

- **Trivial mechanical edits** — just do them.
- **Repeated patterns** — explain the first time, apply silently afterwards.
- **"Just ship it" signals** — collapse to action-only mode for that task.

## Style of explanation

- Show the boring, standard, widely-used approach first; mention fancy alternatives second.
- Introduce jargon, don't assume it.
- When introducing a tool, give one line on its place in the ecosystem.
- Concrete two-line examples beat abstract paragraphs.
- If uncertain, say so — "I think X, but verify before depending on it" beats confident wrong.

## Code conventions — non-negotiable

- Follow `docs/CONVENTIONS.md` and `docs/CODE_STYLE.md` strictly. If silent on a question, ask before deciding.
- One concern per commit. Conventional Commits format.
- Never `git add .` or `git add -A`. Stage explicit paths.
- Never commit `.env` or anything that looks like a secret. The Anthropic API key never appears in code, tests, fixtures, or logs.
- Never push to `main` directly; work on a branch and open a PR.
- Don't skip hooks (`--no-verify`) unless explicitly asked.
- Synthetic data only — no real names, employees, or UBS-internal content in code, fixtures, or issues.

## Folder rules

- `backend/` — Python/FastAPI. `src/` subfolders by purpose: `api/`, `engine/`, `services/`, `models/`, `jobs/`, `db/`, `core/`.
- `frontend/` — React/TS/Vite. The migrated design-system kit lives in `src/components/ui/`; screens in `src/pages/`.
- `docs/` — engineering documentation; new design notes and ADRs go here.
- `deploy/` — docker-compose and deployment glue.

## Decisions made and locked

These are settled across the programme's design phases. If asked about them again, recall the decision and reason rather than relitigating.

- **Python 3.12** with `uv`; **FastAPI**; **structlog**; **pytest**.
- **SQLAlchemy 2.x typed API** + **Alembic**; **PostgreSQL 16** (docker-compose locally); blobs to blob storage, not Postgres.
- **LangGraph** orchestrates the five-stage engine; **Instructor** enforces LLM output schemas.
- **Anthropic** models: Sonnet 4.6 (Contextual Pass, Recommendations), Haiku 4.5 (Judge). Multi-model gateway is post-MVP; don't add abstraction layers for it now.
- **Frontend:** React + TypeScript + Vite + Tailwind + TipTap, managed with `npm`; Recharts on the HR portal.
- **Pre-commit hooks** + **GitHub Actions CI**; **Conventional Commits** with squash-merge.
- **Engine semantics from the [design spec](docs/DESIGN_SPEC.md) are binding:** the Adjudicator's verbatim span check, Fisher's-exact gating on patterns, document-scoped dismissal fingerprints, log-everything-suppress-in-UI, non-blocking flags.

## When to ask vs when to act

- **Ask first:** folder restructuring, swapping a library, schema changes, anything touching the engine's stage contract or the privacy model (manager-only visibility, HR aggregates).
- **Just do it:** bounded, reversible tasks — a described function, a clearly-identified bug, a test.
- **Always ask before:** destructive git operations, migrations against a non-disposable DB, new top-level dependencies.

## When you're stuck

Read the relevant file. If the file doesn't answer it, ask. Don't guess and ship — guessing in a learning project means the owner inherits the wrong mental model.
