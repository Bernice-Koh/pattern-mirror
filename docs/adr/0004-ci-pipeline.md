# 4. CI pipeline (PR quality gate)

- Status: Accepted
- Date: 2026-06-19

## Context

Issue #18 adds the project's first continuous-integration pipeline: a GitHub Actions
workflow that runs on every pull request. It exercises the checks `docs/CONVENTIONS.md`
already mandates — `ruff`, `mypy --strict`, `pytest` — plus the frontend's `eslint`,
`prettier --check`, and production `build`. The database tests require a real PostgreSQL
(CONVENTIONS forbids SQLite stand-ins), and `backend/tests/conftest.py` is already written
to migrate and run against a disposable database in CI.

SonarCloud is named in the issue but deferred to a follow-up PR (see Consequences).

## Decision

- **One workflow, two parallel jobs.** `backend` and `frontend` run concurrently, so the
  wall-clock cost is the slower job rather than the sum, and each reports as its own status
  check. This also keeps the pipeline inside the issue's ~5-minute budget.

- **PostgreSQL as a service container, not docker-compose.** The `backend` job runs
  `postgres:16` as a GitHub Actions service, health-gated with `pg_isready` so tests start
  only once the database answers. `deploy/docker-compose.yml` exists for local dev (a named
  volume, the test-DB init script); CI wants an ephemeral instance with nothing persisted.

- **The suite resolves its own database.** Actions sets `CI=true` automatically; with
  `TEST_DATABASE_URL` left unset, `conftest.py` migrates and runs against the job's
  `DATABASE_URL` — the service container — so no init script is needed in CI.

- **Locked, reproducible installs.** `uv sync --locked` and `npm ci` both fail on a stale
  lockfile, so CI guards reproducibility as well as correctness.

- **Pinned toolchain.** Python via `backend/.python-version` (3.12), Node via
  `frontend/.nvmrc`, and pinned action major-versions, so a runner-side change cannot
  silently alter behaviour.

- **Least privilege.** The workflow grants the token `contents: read` only.

## Consequences

- **+** Every PR gets lint, type, test, and build feedback automatically, on a clean machine —
  catching lockfile drift and environment assumptions a local run would miss.
- **+** The identical workflow becomes a *required* check with no edits the day the repo can
  enforce one.
- **−** **No merge enforcement yet.** Required status checks / branch protection are a GitHub
  capability unavailable on a free private repository. Until the repo moves to Pro or becomes
  public, the pipeline reports status and the working convention is "don't merge red", backed
  by local pre-commit hooks (a separate issue). Issue #18's acceptance criteria were reworded
  from "cannot be merged" to reflect this honestly.
- **−** SonarCloud is excluded here: it needs an external project and a `SONAR_TOKEN` secret,
  and including an unprovisionable check would block the very PR that introduces the gate. It
  lands as its own PR once provisioned.

## Alternatives considered

- **`docker compose up` in CI** instead of a service container — rejected: it pulls in the
  local-dev volume and init script for no CI benefit; the service container is the idiomatic,
  ephemeral choice and is health-gated the same way.
- **SQLite for tests in CI** — rejected outright: CONVENTIONS requires real PostgreSQL, and
  the foundation schema uses Postgres-specific types the engine depends on.
- **A single job running every check sequentially** — rejected: slower wall-clock and one
  conflated pass/fail; parallel jobs give per-concern signal and fit the time budget.
