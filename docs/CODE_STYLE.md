# Code Style

Language-level rules for writing code in this repo. Workflow, folder structure, testing strategy, and git rules live in [CONVENTIONS.md](CONVENTIONS.md) — this file is only about how the code itself reads.

Each rule has a short *why* attached. Knowing *why* lets you make judgement calls on the edge cases the rules don't cover.

## Universal principles

### Comments are for *why*, not *what*

Code is for *what*. If a comment restates what the code does, delete it or rewrite the code so the comment isn't needed.

> *Why:* "what" comments rot — the code changes, the comment doesn't. "Why" comments rarely rot, because the reason for a decision usually outlives the decision.

`# HACK:` and `# FIXME:` are fine, with a date and brief context.

### Names carry the explanation

Prefer a longer, clearer name over a shorter name plus a comment.

> *Why:* names appear at every call site; a comment appears once.

`compute_sentence_fingerprint()` beats `hash()` with a docstring. `is_suppressed_by_dismissal` beats `flag2`.

### Boundary checks vs internal trust

Validate inputs at system boundaries: HTTP request bodies, LLM structured outputs, external API responses. Inside a module, trust the types and don't re-validate.

> *Why:* one layer of strict validation at the boundary protects everything inside; defensive checks everywhere rot independently and bury the logic.

In this project the LLM is a boundary. Every Contextual Pass / Judge / Recommendations response is parsed into a Pydantic schema (via Instructor) before any other code touches it. Raw model text never flows through the engine.

---

## Python

### Type hints everywhere

Every function signature has parameter and return type hints. Modern union syntax (`str | None`, not `Optional[str]`).

> *Why:* `mypy --strict` is gated in CI, and types are the most honest documentation — they can't be wrong without breaking the build.

### Docstrings

Google-style docstrings on every public function and class. Module docstring at the top of every file: one to three sentences on purpose.

```python
def adjudicate_flags(flags: list[CandidateFlag], source_text: str) -> AdjudicationResult:
    """Drop any flag whose claimed span is not verbatim in the source; keep the rest.

    Args:
        flags: Candidate flags from the dictionary and contextual stages.
        source_text: The exact document text the manager submitted.

    Returns:
        The verified survivors and the rejected flags, each carrying its reason.
    """
```

Private helpers (`_leading_underscore`) can skip docstrings if the name and signature are obvious.

### Naming

| Kind | Convention | Example |
|---|---|---|
| Modules, files | `snake_case` | `dictionary_service.py` |
| Functions, variables | `snake_case` | `compute_lemma_bag()` |
| Classes | `PascalCase` | `PatternAggregator` |
| Constants | `UPPER_SNAKE` | `JUDGE_CONFIDENCE_THRESHOLD` |
| "Private" by convention | leading `_` | `_normalise_span()` |

### Module structure

A module has one purpose, stated in its docstring. If it gains a second purpose, split it.

### Pydantic vs SQLAlchemy vs dataclass

| Use | When |
|---|---|
| `pydantic.BaseModel` | Anything crossing a system boundary: HTTP bodies, structured LLM outputs (Instructor), config from `.env`. |
| SQLAlchemy `Mapped[...]` model | Anything mapping to a database table. Lives in `models/`. Never returned directly from API handlers. |
| `@dataclass` | Plain internal value objects passed between engine stages, no validation, no DB mapping. |

> *Why:* a SQLAlchemy model returned from a handler leaks DB columns into the public API; Pydantic as an ORM gives up relationship management. The layer boundary is exactly where the type changes.

### FastAPI handler patterns

Handlers in `api/` are thin: typed request model in, `Depends(...)` for session/deps, one call into `services/` or the orchestrator, typed response model out. Exceptions map to HTTP responses via exception handlers, not per-handler `try/except`.

> *Why:* five-line handlers mean business logic is reachable from jobs, tests, and other entrypoints — and the engine can be tested without HTTP.

### SQLAlchemy patterns

- 2.x typed declarative API (`Mapped[...]`, `mapped_column(...)`); legacy `Column(...)` style is out.
- One `Base`, in `db/base.py`. Sessions scoped per-request or per-job-run, never global.
- Queries via `select(...)`; drop to raw SQL only where the ORM gets ugly (the Pattern Aggregator's contingency-table queries may qualify) and keep it visible in `db/queries/`.

### Async vs sync

This backend has two genuinely different paths, and the rule differs by path:

- **The analysis path is async.** SSE streaming of flags plus multi-second Anthropic calls is the textbook case: `async` handlers let the server stream Layer 1 dictionary flags while the Layer 2 LLM call is still in flight, and keep other requests unblocked.
- **Everything else defaults to sync.** CRUD endpoints, the Pattern Aggregator's SQL, jobs — sync is simpler to write, debug, and test, and there's no concurrency win to pay async's call-chain contagion for.

> *Why:* async is a cost (every caller in the chain must be async) that's only worth paying where you actually wait on slow I/O concurrently. Pay it on the engine path; refuse it elsewhere.

### Exceptions

- Typed exceptions in `core/errors.py`, all subclassing `PatternMirrorError`.
- Raise at the deepest layer that can name the failure (`SpanNotInSource`, not `ValueError`).
- Catch at handler/orchestrator boundaries only.

---

## TypeScript

### Strict mode, no escape hatch

`strict: true`; no `any` without a `// reason:` comment.

> *Why:* `any` is contagious — one `any` return type infects every caller.

### Naming

| Kind | Convention | Example |
|---|---|---|
| Files | `kebab-case.tsx` | `flag-underline.tsx` |
| Components | `PascalCase` | `FlagUnderline` |
| Types, interfaces | `PascalCase` | `FlagResponse` |
| Functions, variables, hooks | `camelCase` | `useFlagStream` |
| Constants | `UPPER_SNAKE` | `SSE_RETRY_MS` |

> *Why:* kebab-case files avoid cross-platform case-sensitivity bugs (`Flag.tsx` vs `flag.tsx` silently breaks between Windows and Linux).

### One exported component per file

Unless tightly coupled (a list and its item). File path = component identity.

### JSDoc on exports only

Short JSDoc explaining *intent* on public components and exported functions; internal helpers skip it.

### State management

- Local state (`useState`, `useReducer`) is the default.
- Server state (flags, patterns, documents from the API) goes through TanStack Query — Layer 1's request/response `/analyze` call included. Don't mirror server state into a global store.
- A long-lived SSE subscription that *accumulates* incrementally (the Layer 2 flag stream) is the exception: it lives in a dedicated hook owning its `AbortController` and accumulator, not on TanStack Query. Query models one request resolving to one response, not an open stream appending results over seconds.
- Global UI state (active view, sidebar) — Context if tiny, Zustand if it grows.

> *Why:* the classic mistake is putting server data in a global store and hand-writing a sync layer; server-state libraries solve caching, loading states, and refetching for free. The carve-out is narrow — only the accumulating stream, because the abstraction Query is built around (request → response) doesn't fit it.

### Styling

Tailwind utility classes in JSX are the styling mechanism — that's the stack's model, not a violation of separation.

- Repeated utility patterns get extracted into a component (or a `cva`/variant helper), not copy-pasted across files and not hidden in `@apply` blobs.
- No `style={{ ... }}` inline style objects; if a value must be dynamic, prefer a CSS variable set at a high level.
- `!important` is banned except against third-party CSS, with a comment.

> *Why:* the unit of reuse in a Tailwind codebase is the component, not the class string. Extracting components keeps the design system (the migrated `pm` kit) the single source of visual truth.

### Imports

- Absolute `@/` imports for anything in `src/`; relative only for siblings.
- Group: external, then `@/internal`, then sibling. Named imports only, never `import *`.

---

## Cross-language

### File length

Over ~400 lines, ask whether the file has more than one purpose. It almost always does.

### Tests mirror source

`backend/src/pattern_mirror/engine/adjudicator.py` → `backend/tests/engine/test_adjudicator.py`. You should never have to ask where a file's tests are.

### Dead code

Delete it. Git remembers; the codebase shouldn't carry corpses.
