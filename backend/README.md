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
