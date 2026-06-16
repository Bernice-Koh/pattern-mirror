# 2. Frontend foundation stack

- Status: Accepted
- Date: 2026-06-16

## Context

Issue #15 builds the first frontend code: a real Vite + React + TypeScript (strict) app
shell that compiles at build time (no in-browser transpilation), with five placeholder
surface routes and the core component set. `docs/CONVENTIONS.md` already fixes React +
TypeScript + Vite + Tailwind + npm; three choices it leaves open needed deciding.

## Decision

- **Routing — TanStack Router (code-based).** All routes are declared in
  `frontend/src/router.tsx`, referencing the screen components in `frontend/src/pages/`.
  Chosen over React Router for end-to-end type safety and consistency with TanStack Query
  (already mandated for server state). Code-based routing (rather than the plugin's
  file-based generation) suits our five flat routes: no codegen step and no generated
  `routeTree.gen.ts` in version control.

- **Styling — Tailwind v4 + `@tailwindcss/vite`.** The adopted tokens are bridged to
  utilities with `@theme inline` in `src/index.css`, so `bg-red-primary` references
  `var(--red-primary)` and the token files stay the source of truth. Chosen over v3 as the
  current default for new Vite projects with the cleanest token bridge.

- **Variants — class-variance-authority** (with `clsx` + `tailwind-merge` behind a `cn()`
  helper) for variant×size component matrices, as endorsed by `docs/CODE_STYLE.md`.

- **`base.css` in Tailwind's `base` layer.** Tailwind v4 puts preflight/utilities in
  cascade layers; the adopted `base.css` is imported with `layer(base)` so utility classes
  always win over element defaults (an unlayered `p { margin: 0 }` would otherwise beat
  `mt-4`).

## Consequences

- **+** Strict, type-safe routing and styling that match repo conventions.
- **+** The route tree is plain, reviewable TypeScript — no codegen step or generated file.
- **−** TanStack Router has a smaller ecosystem than React Router; acceptable given the
  type-safety win and our flat route set.
- **−** Code-based routing is more verbose per route than file-based and does not
  auto-split route bundles; fine at this size.

## Alternatives considered

- **React Router v7** — the standard, best-documented router; rejected only because our
  routes are simple and TanStack's type safety + Query synergy win for a strict-TS codebase.
- **TanStack Router file-based routing** — the maintainers' recommended default; deferred
  because our flat route set doesn't need codegen, and it keeps a generated file out of
  version control.
- **Tailwind v3** — more tutorials, explicit `tailwind.config` object; rejected as the
  legacy setup for greenfield work.
