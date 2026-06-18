# pattern-mirror backend

Python 3.12 / FastAPI service for the pattern-mirror analysis engine and API.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) for environment and dependency management

## Setup

All backend commands run from this `backend/` directory:

```bash
cd backend
```

1. **Create your `.env`** from the template (it lives here in `backend/` and is
   loaded relative to this directory):

   ```bash
   cp .env.example .env            # PowerShell: Copy-Item .env.example .env
   ```

   The skeleton currently reads `APP_ENV` (required) and `LOG_LEVEL` (defaults to `INFO`). The template's other variables are placeholders consumed by the issues that introduce the database, LLM, and blob-storage code.

2. **Install dependencies** (creates `backend/.venv` and resolves `backend/uv.lock`):

   ```bash
   uv sync
   ```

3. **Start Postgres** (from the repo root). The container provisions both the
   dev database and the isolated test database on first boot:

   ```bash
   docker compose -f deploy/docker-compose.yml up -d
   ```

4. **Apply migrations** to reach the full schema (run from `backend/`):

   ```bash
   uv run alembic upgrade head
   ```

## Database and migrations

- **Schema source of truth is the Alembic migration history**, not the model
  classes. Models live in `src/pattern_mirror/models/`; the migrations in
  `src/pattern_mirror/db/migrations/versions/`.
- Generate a revision after changing models, then read and edit it before
  committing. Use a sequential id matching the design roadmap:

  ```bash
  uv run alembic revision --autogenerate --rev-id 0002 -m "recommendations"
  uv run alembic check          # fails if models and migrations disagree
  uv run alembic upgrade head
  uv run alembic downgrade -1   # verify the down path too
  ```

- Native enum *value* changes are not autodetected; add them with a hand-written
  `op.execute("ALTER TYPE ... ADD VALUE ...")`.

## Run

```bash
uv run uvicorn pattern_mirror.main:create_app --factory --reload
```

The `--factory` flag tells uvicorn to call `create_app()` to build the app, so importing the module has no side effects but a missing variable still aborts boot. Then:

- Healthcheck: <http://localhost:8000/health>
- API docs (Swagger UI): <http://localhost:8000/docs>

If a required variable is missing, startup fails immediately with a validation error naming the offending field.

## Checks

```bash
uv run ruff check src tests       # lint
uv run ruff format src tests      # format
uv run mypy src                   # strict type-check
uv run pytest                     # tests
```
