# Design system (in-repo)

Pattern Mirror's UI is built from a design handoff produced in Claude Design. This folder
documents how that handoff was adopted and how to extend the in-repo design system.

The handoff bundle (`pattern-mirror-design-system/` at the repo root) is **read-only
reference and gitignored** — never commit from it. See
[ADR 0001](../adr/0001-design-handoff-adoption.md) for the adoption policy and
[ADR 0002](../adr/0002-frontend-foundation-stack.md) for the stack.

## What was adopted

| From the handoff                                          | Treatment                                                        | Lands in                       |
| -------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------ |
| `tokens/*.css`                                           | Copied — values are the source of truth; comments/formatting normalised | `frontend/src/styles/tokens/`  |
| `*.d.ts` prop interfaces                                 | Contracts our components satisfy                                 | (not imported; authored against) |
| `*.jsx`, bundles, preview HTML, `ui_kits/`, assets       | Reference only — never committed                                 | —                              |

## Where things live

- `frontend/src/styles/tokens/*.css` — the adopted token files (colour, type, spacing, WFA
  palette, base element styles, fonts).
- `frontend/src/index.css` — the app CSS entry: loads fonts, Tailwind, the tokens, then the
  token→utility **bridge** (`@theme inline`).
- `frontend/src/components/ui/*.tsx` — the authored components.

## Tokens as Tailwind utilities (the bridge)

The tokens are plain CSS custom properties (`--red-primary`, `--radius-card`, …). Tailwind
v4 only turns variables declared in `@theme` into utilities, so `index.css` bridges each:

```css
@theme inline {
  --color-red-primary: var(--red-primary);
  --radius-card: var(--radius-card);
}
```

`inline` makes the generated utility _reference_ the token (`background-color:
var(--red-primary)`), so the token files remain the single source of truth — edit a token
and every utility re-themes. This yields utilities such as `bg-red-primary`,
`text-ink-muted`, `rounded-card`, `text-micro`, `shadow-ring-card`, `font-serif`, and the
`wfa-*` colours. The eyebrow label keeps the adopted `.pm-eyebrow` class from
`typography.css`.

Spacing uses Tailwind's default 4px scale, which matches the token `--space-*` values
(`p-6` = 24px), so spacing is not bridged.

## Fonts

The brand fonts (UBS Serif / UBS Sans) are proprietary and not bundled. `fonts.css`
substitutes the closest open Google Fonts — **Source Serif 4** (display) and **Inter**
(UI).

## Component contracts

Each authored component satisfies a prop interface from the handoff:

| Component  | Contract (handoff)   | Renders                                                          |
| ---------- | -------------------- | --------------------------------------------------------------- |
| `Button`   | `core/Button.d.ts`   | `<button>` — variant (primary/secondary/ghost) × size           |
| `Badge`    | `core/Badge.d.ts`    | `<span>` — tone red/neutral/green                               |
| `Chip`     | `core/Chip.d.ts`     | `<span>` — inert, or `active` red-tint                          |
| `TopBar`   | `app/TopBar.d.ts`    | `<header>` — wordmark + breadcrumb / chips + avatar (+ action)  |
| `FlagCard` | `flags/FlagCard.d.ts`| `<div>` — evidence + alternatives + Apply/× (Undo when dismissed)|

`TopBar` renders a text wordmark and an initials avatar inline (the handoff's `Wordmark` /
`Avatar` are not in this set); `FlagCard` renders suggestion pills inline (handoff
`SuggestionChip`). Keeping these inline holds the exported set to exactly the five contracts.

## Adding a component against a contract

1. Read the contract `.d.ts` in the handoff
   (`pattern-mirror-design-system/project/components/...`).
2. Read its `.prompt.md` (and `.jsx` for _visual reference only_ — do not copy it).
3. Author `frontend/src/components/ui/<name>.tsx` (kebab-case file, PascalCase export):
   - Props that satisfy the contract; extend the matching `React.*HTMLAttributes`.
   - Tailwind utilities over the adopted tokens — no inline `style`, no hard-coded px, no
     `useState` hover (use `hover:` variants). Use `cva` for variant matrices and `cn()` to
     merge an incoming `className`.
4. Run `npm run lint && npm run build` to check lint and types.

## Never commit from the handoff

`*.jsx`, `_ds_bundle.js`, `_ds_manifest.json`, every `(offline).html` /
`(standalone-src).html` / print / preview page, `ui_kits/`, the loader page,
`_adherence.oxlintrc.json`, and image assets. The whole `pattern-mirror-design-system/`
folder is gitignored.
