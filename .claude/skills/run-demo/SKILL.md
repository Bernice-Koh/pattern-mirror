---
name: run-demo
description: "Launch and drive the full pattern-mirror stack (Postgres + FastAPI backend + Vite frontend) for a demo, with warm/cold-start handling, port-sprawl cleanup, and demo logins. Use when asked to run, start, or demo the app end-to-end."
trigger: /run-demo
---

# /run-demo

Bring up the whole stack on the canonical ports and verify it end-to-end:

- **Postgres** — Docker, `localhost:5432`
- **Backend** — FastAPI, `http://localhost:8000`
- **Frontend** — Vite, `http://localhost:5173`

The frontend proxies API paths to the backend (see `server.proxy` in
`frontend/vite.config.ts`), so the browser sees one origin and there is no CORS
in dev. The proxy targets `localhost:8000` — keep the backend on that port.

## Prerequisites

Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22. Confirm:

```bash
docker version --format '{{.Server.Version}}'
uv --version
node --version
```

## Step 0 — warm or cold?

Check what already exists so you don't redo provisioning. Run from repo root:

```bash
docker ps --format '{{.Names}}\t{{.Status}}' | grep pattern-mirror-postgres   # DB up?
ls backend/.venv >/dev/null 2>&1 && echo "backend venv: yes" || echo "backend venv: no"
ls frontend/node_modules >/dev/null 2>&1 && echo "frontend deps: yes" || echo "frontend deps: no"
ls backend/.env >/dev/null 2>&1 && echo "backend .env: yes" || echo "backend .env: no"
```

- **Cold** (anything missing) — run every step below.
- **Warm** (all present) — skip `docker compose up`, `uv sync`, and
  `npm install`; still run migrations and the seed (both idempotent).

## Step 1 — Postgres

```bash
docker compose -f deploy/docker-compose.yml up -d
```

The init scripts in `deploy/postgres-init/` provision the isolated test database
alongside the dev one; they run once, on first boot of an empty volume.

## Step 2 — Backend (`http://localhost:8000`)

```bash
cd backend
cp .env.example .env          # cold start only; add ANTHROPIC_API_KEY for the LLM stages
uv sync                        # cold start only
uv run alembic current         # expect the latest revision as "(head)"
uv run alembic upgrade head    # no-op if already at head
uv run python -m pattern_mirror.jobs.seed_demo   # idempotent by external_user_id
uv run uvicorn pattern_mirror.main:create_app --factory --host 127.0.0.1 --port 8000
```

Without `ANTHROPIC_API_KEY` the deterministic stages still run — dictionary flags
work and the LLM stages pass through. With the key set, the contextual pass, judge,
and recommendations are live.

## Step 3 — Frontend (`http://localhost:5173`)

Second shell:

```bash
cd frontend
npm install                                    # cold start only
npm run dev -- --port 5173 --strictPort
```

`--strictPort` is deliberate. Without it Vite silently walks to the next free port
(5174, 5175, ...) when 5173 is taken, which is how stale servers pile up across
sessions and you lose track of your own URL. With it, Vite fails loudly if 5173 is
occupied — clear the port (see cleanup) rather than drifting to another.

## Step 4 — verify end-to-end

Hit the backend directly and through the proxy. A `401` on an authenticated route
still proves the proxy reached the backend.

```bash
curl -s http://127.0.0.1:8000/health                      # {"status":"ok",...}
curl -s http://localhost:5173/ | grep -i '<title>'        # Pattern Mirror

# manager login through the proxy, then fetch patterns
T=$(curl -s -X POST http://localhost:5173/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"alex.tan@example.com","password":"x","expected_role":"manager"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -s http://localhost:5173/patterns -H "Authorization: Bearer $T" | head -c 200
```

Open `http://localhost:5173` and log in.

## Demo logins

Mock auth: the email identifies the user, `expected_role` picks the portal, and the
password is any non-empty string. Managers come from the seed dataset; the HR
reviewer is fixed in code.

| Portal | Email | Role |
|---|---|---|
| Manager | `alex.tan@example.com` | manager |
| Manager | `priya.sharma@example.com` | manager |
| Manager | `marcus.wong@example.com` | manager |
| HR | `jordan.lee@example.com` | hr |

Manager emails are defined in `backend/src/pattern_mirror/jobs/seed_data/demo_dataset.json`;
the HR user is in `seed_demo.py`. If the dataset changes, re-read them from there.

## Cleanup — stray servers on the demo ports

Destructive: this kills processes. Do it deliberately, only when a port you need is
occupied by a leftover server from a previous session. Confirm what you're killing
first — never kill a PID you haven't identified.

```bash
# See what holds the demo ports
netstat -ano | grep LISTENING | grep -E ':(5173|5174|5175|5176|5177|8000)\s'

# Kill a specific PID once identified (Git Bash needs the double slash)
taskkill //PID <pid> //F
```

Prefer `--strictPort` (Step 3) so sprawl doesn't happen in the first place. If you
find a backend already on 8000, confirm it's this app before reusing or killing it:

```bash
curl -s http://127.0.0.1:8000/openapi.json | head -c 80    # title should be "pattern-mirror"
```

## Stopping the demo

`Ctrl+C` the two server shells. Leave Postgres running for next time, or stop it:

```bash
docker compose -f deploy/docker-compose.yml down       # add -v to also drop the data volume
```
