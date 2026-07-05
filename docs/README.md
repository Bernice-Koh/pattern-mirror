# Documentation index

| Document | What it is | Audience |
|---|---|---|
| [DESIGN_SPEC.md](DESIGN_SPEC.md) | The captured product design specification — the product source of truth | Everyone; binding on engine semantics |
| [architecture/overview.md](architecture/overview.md) | The system as built: boundaries, engine shape, data paths | Anyone reading or reviewing the code |
| [architecture/llm-judge.md](architecture/llm-judge.md) | The LLM Judge: rubric scoring, self-consistency confidence, calibration | Anyone interested in the LLM-as-judge design |
| [CONVENTIONS.md](CONVENTIONS.md) | How we work: folder structure, testing, git, PRs, project management | Contributors |
| [CODE_STYLE.md](CODE_STYLE.md) | Language-level style rules for Python and TypeScript | Contributors |
| [adr/](adr/) | Architecture decision records — what was decided, when, and why | Anyone asking "why is it like this?" |
| [design-system/](design-system/README.md) | How the design handoff was adopted into the frontend | Frontend contributors |
| [references/](references/) | Source excerpts backing dictionary content | Dictionary curators |

Architecture docs describe current state and change with the code; ADRs are immutable
records of decisions at a point in time. When they disagree, the ADR is history and the
architecture doc is the bug.
