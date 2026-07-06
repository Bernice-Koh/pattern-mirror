# Pattern Mirror — frontend

React + TypeScript + Vite single-page app for the Pattern Mirror manager and HR
surfaces. See [docs/adr](../docs/adr) for the foundation decisions.

## Commands

```sh
npm install      # install dependencies
npm run dev      # start the dev server
npm run build    # type-check (tsc) and build for production
npm run lint     # eslint
npm run format   # prettier --write
```

## Layout

- `src/components/ui/` — design-system components, authored against the handoff contracts
- `src/pages/` — surface screens
- `src/router.tsx` — route table (code-based TanStack Router)
- `src/styles/tokens/` — adopted design tokens
- `src/index.css` — Tailwind entry and the token → utility bridge
