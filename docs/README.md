# Documentation index

| Document | What it is | Audience |
|---|---|---|
| [DESIGN_SPEC.md](DESIGN_SPEC.md) | The captured product design specification — the product source of truth | Everyone; binding on engine semantics |
| [architecture/overview.md](architecture/overview.md) | The system as built: boundaries, engine shape, data paths | Anyone reading or reviewing the code |
| [architecture/llm-judge.md](architecture/llm-judge.md) | The LLM Judge: rubric scoring, self-consistency confidence, calibration | Anyone interested in the LLM-as-judge design |
| [architecture/flags-and-suppression.md](architecture/flags-and-suppression.md) | Flag identity: signatures, sentence fingerprints, dismissal suppression | Anyone touching flag persistence or dismissals |
| [architecture/dictionary-growth.md](architecture/dictionary-growth.md) | How the dictionary learns: trigger, four-agent debate, HR approval | Anyone touching the growth loop or dictionary |
| [architecture/pattern-significance.md](architecture/pattern-significance.md) | Why a pattern surfaces: Fisher's exact gating on the dashboard | Anyone touching the Pattern Dashboard or aggregator |
| [project-management.md](project-management.md) | How the project is run: sprints, epics/issues, how changes ship | Non-technical readers; anyone curious how it's delivered |
| [architecture/data-model.md](architecture/data-model.md) | ER map of the core entities and the columns that earn an explanation | Anyone touching models or migrations |
| [CONVENTIONS.md](CONVENTIONS.md) | How we work: folder structure, testing, git, PRs, project management | Contributors |
| [CODE_STYLE.md](CODE_STYLE.md) | Language-level style rules for Python and TypeScript | Contributors |
| [adr/](adr/) | Architecture decision records — what was decided, when, and why | Anyone asking "why is it like this?" |
| [references/](references/) | Source excerpts backing dictionary content | Dictionary curators |

Architecture docs describe current state and change with the code; ADRs are immutable
records of decisions at a point in time. When they disagree, the ADR is history and the
architecture doc is the bug.
