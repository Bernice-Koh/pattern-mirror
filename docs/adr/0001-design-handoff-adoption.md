# 1. Design-handoff adoption policy

- Status: Accepted
- Date: 2026-06-16

## Context

The visual design for Pattern Mirror was produced in Claude Design and exported as a
handoff bundle (`pattern-mirror-design-system/`, kept at the repo root as read-only
reference). The bundle contains three kinds of thing:

- **Design tokens** — `project/tokens/*.css` and `project/styles.css`: CSS custom
  properties for colour, type, spacing, radius, shadow, and the WFA bias-type palette.
- **Component type declarations** — `*.d.ts` files describing each component's props.
- **Prototype implementations** — `*.jsx`, the bundled `_ds_bundle.js`, `(offline).html`
  / `(standalone-src).html` preview pages, `ui_kits/`, a loader page,
  `_adherence.oxlintrc.json`, and image assets.

The prototypes are HTML/CSS/JS mockups: they use inline `style` objects, hard-coded
pixel values, and `useState`-driven hover — all banned by `docs/CODE_STYLE.md`. They are
a visual spec, not production code.

We need a rule for what crosses from the handoff into the repo, so adoption is faithful
to the design without importing prototype patterns we've outlawed.

## Decision

Three categories, three treatments:

1. **Tokens = data.** The token files (`tokens/*.css`) are copied into
   `frontend/src/styles/tokens/` and wired through `frontend/src/index.css`, which also
   bridges them to Tailwind utilities. The token *values* are the single source of visual
   truth; comments and formatting are normalised to the repo standard, with no token value
   or selector changed. The handoff's `styles.css` aggregator is **not** adopted —
   `index.css` imports the token files directly so it can place `base.css` in Tailwind's
   `base` layer, which a flat `@import` list cannot express.

2. **Declarations = contracts.** The five `.d.ts` prop interfaces (Button, Badge, Chip,
   TopBar, FlagCard) are the contracts our components must satisfy. We author props that
   match them; we do not import the `.d.ts` files themselves.

3. **Implementations = authored.** Every component is written from scratch in `.tsx`
   against its contract, styled with Tailwind utilities over the adopted tokens. No
   prototype `.jsx` — and none of its banned patterns — enters the repo.

Everything else in the bundle is **reference-only and never committed**: all `.jsx`,
`_ds_bundle.js`, `_ds_manifest.json`, every preview/print HTML page, `ui_kits/`, the
loader page, `_adherence.oxlintrc.json`, and image assets. The entire
`pattern-mirror-design-system/` folder is gitignored.

## Consequences

- **+** The design's visual decisions (the actual token values) are adopted exactly,
  while implementation follows our code style.
- **+** Contracts give components a stable, design-authored API without coupling to
  prototype code.
- **+** Re-generating the design (a new handoff) only touches tokens and contracts; our
  `.tsx` is unaffected unless a contract changes.
- **−** Token values are duplicated from the handoff into the repo; a re-export means a
  deliberate, reviewable re-copy.
- **−** Because we re-format and re-comment the adopted CSS, byte-for-byte diffing against
  the handoff no longer proves fidelity; provenance is recorded here and in
  `docs/design-system/` instead.

## Notes

The brand fonts (UBS Serif / UBS Sans) are proprietary and not in the bundle; the tokens
substitute the closest open Google Fonts (Source Serif 4 / Inter). Replace with licensed
fonts for production. See `docs/design-system/README.md`.
