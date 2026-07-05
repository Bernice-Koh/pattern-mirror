# Pattern significance

The Pattern Dashboard tells a manager things like *"'aggressive' appears in your
feedback about men far more than about women."* That is an accusation with weight, and
made carelessly it destroys the product: one coincidence presented as a pattern and
the manager writes the whole dashboard off. So a pattern must clear a statistical bar
before it surfaces — frequency alone is never enough. No LLM is involved anywhere on
this path; it is queries and arithmetic (`services/pattern_aggregator.py`,
`services/significance.py`).

## The question the test answers

"This term shows up more in group A's documents than group B's" can always be true by
chance, especially with the small document counts one manager produces. Fisher's exact
test takes a 2×2 table of counts and answers: *if the term actually had nothing to do
with the group, how likely is a split at least this lopsided?* That likelihood is the
p-value. Small p-value → hard to explain away as chance → the pattern surfaces.

Concretely, for one term across one manager's feedback documents:

|  | about men | about women |
|---|---|---|
| documents flagging "aggressive" | 6 | 1 |
| documents not flagging it | 2 | 7 |

Fisher's exact on this table gives p ≈ 0.04: fewer than a 5-in-100 chance of a split
this skewed arising with no real association. Under the default threshold of 0.05 this
pattern surfaces. The same counts spread over fewer documents — say 3/1 against 1/3 —
give p ≈ 0.49, and nothing surfaces: too little data to call it anything but noise.

Why *Fisher's exact* specifically: it is exact for small samples, unlike the more
common chi-squared test, which approximates and needs expected cell counts a single
manager's history rarely provides. Small-count 2×2 tables are precisely its home turf,
and it costs one `scipy.stats.fisher_exact` call (the only scipy use in the codebase).

## What gets tested

Two families of pattern, both per manager, both gated the same way:

**Writing patterns** — does a flagged term track a subject demographic?
For each term × bias category over the manager's subject documents (feedback and
promotion write-ups, grouped by the subject's gender for MVP), the table above is
built and tested. Two modes run:

- **across-time** — the manager's whole history, one test per term.
- **per-role** — documents grouped by the JD they reference (falling back to role
  title), testing within a single role's candidate pool, where "same term, different
  groups" is hardest to explain innocently.

**Decision patterns** — does the manager treat one bias category differently?
Each flag ends in a behavioural state
([overview](overview.md#the-two-data-paths)); states where the flagged language was
removed or revised count as *adoption*. Per category, a 2×2 of adopted/rejected in
this category vs all other categories asks: is the manager's adoption rate for, say,
age flags significantly lower than their rate everywhere else? A manager who fixes
every gendered phrase but dismisses every age-related one has a pattern in their
*decisions*, not just their words.

## The gate

- The threshold is config, not code: `pattern_significance_threshold`, default 0.05
  — the conventional bar for "unlikely to be chance", not a magic number.
- The boundary is **exclusive**: p must be strictly below the threshold
  (`is_significant`, `services/significance.py`).
- An empty table returns p = 1.0 — nothing to test is never significant.
- Fewer than two comparison groups → no test runs at all; a manager who has only
  written about one group can't have a between-group pattern.
- Surfaced patterns are sorted by ascending p-value: strongest evidence first.

## What this protects

- **The manager's trust.** Every dashboard claim can say "this is statistically
  unlikely to be chance", with the counts and p-value on the record.
- **The mirror-not-judge stance.** The dashboard reports associations in the
  manager's own writing with the evidence attached; it never extrapolates from
  anecdote.
- **Honesty about thin data.** A new manager with five documents sees no patterns —
  correctly. The dashboard staying quiet is the statistics working, not a bug: the
  patterns appear as the history accumulates.
