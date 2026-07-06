# Project management

Pattern Mirror is a solo, four-week build for the UBS Tomorrow's Talent Programme 2026,
run with the standard lightweight agile practices. This page explains how the work is
organised, for a non-technical reader. Developer-facing rules are in
[CONVENTIONS.md](CONVENTIONS.md).

## Weekly cadence

Work ships in one-week sprints. Each week commits to a small set of goals; at the end
the work is reviewed and the next week is planned with what was just learned. Only the
current week is planned in detail — planning further ahead wastes effort when priorities
shift.

| Term | Meaning here |
|---|---|
| **Sprint** | One week of committed work. |
| **Standup** | A regular check-in with the programme mentor and engineering buddy: done, next, blocked. |
| **Milestone** | A fixed programme deadline (checkpoints, final showcase). Sprints aim at these. |

## Breaking work down

The product is too large to build in one go, so it is split into smaller pieces until
each is a single, concrete task. Work is tracked in **GitHub Issues**, in three levels:

| Level | What it is | Example |
|---|---|---|
| **Epic** | A whole feature area, weeks of work. | *Analysis Engine* |
| **Nested epic** | A major component within an epic. | *Bias Detection Pipeline* |
| **Issue** | One buildable task with a clear "done". | *Adjudicator span verification* |

A single umbrella epic (*Pattern Mirror MVP*) sits above the rest, so the full scope is
traceable from one place down to the smallest task. Keeping issues small means each one
can be finished, reviewed, and merged on its own.

## How changes ship

Each issue is built on its own branch and merged through a pull request — nothing goes
straight to the main codebase. An issue is done when its code is reviewed and its pull
request is merged, not when it works locally.

| Practice | Reason |
|---|---|
| **One concern per pull request** | Small enough to review in one sitting; two features means two pull requests. |
| **Branch, then pull request** | Work merges only after review, so `main` always works. |
| **Every pull request links its issue** | States what changed, why, and how to test — the trail from task to shipped code stays intact. |
| **Automated checks before merge** | Formatting, type-checking, and tests run on every pull request and must pass to merge. |
