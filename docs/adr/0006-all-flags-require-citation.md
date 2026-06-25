# 6. All flags require a citation (by reference)

- Status: Accepted
- Date: 2026-06-25

## Context

§1 makes "evidence for every flag" a core principle, and §3 Stage 1 has every dictionary
hit cite TAFEP or peer-reviewed research. But §4's dictionary-growth loop states that a
phrase lacking academic or regulatory support "may still fire from the Contextual Pass, but
it does not become a dictionary entry without citation" — i.e. a Contextual Pass (Stage 2)
flag could reach the manager **without** a citation. That is exactly the "the model said so"
dismissal the dictionary exists to defend against (§4), and it is the difference between a
defensible audit trail and an opinion.

## Decision

- **Every flag — dictionary or contextual — carries a citation by reference.** The flag
  references a `citation_id` (FK into the `citations` table); the model never emits
  free-text citations, which would be fabricable.
- **Minimum bar:** the category-level TAFEP citation for the flag's bias category; a sharper
  research citation where one applies.
- **No citation, no flag.** If the Contextual Pass cannot attach a valid `citation_id` to a
  candidate, it suppresses the candidate rather than raising it. The phrase can still enter
  the §4 growth queue, where the Citation agent searches for support.
- **Supersedes** §4's "may still fire from the Contextual Pass [without citation]" wording.

## Consequences

- **+** Defensibility is uniform across stages; no flag rests on "because the model said so".
- **+** The Recommendations precondition (§7, "anchored to citations") is always satisfiable.
- **−** Every MVP bias category must have at least one category-level citation seeded in
  `citations`, or contextual flags in that category cannot fire.
- **−** A genuine bias phrase with no citation yet is not surfaced as a flag; it relies on
  the growth loop to acquire one first.

## Alternatives considered

- **Keep §4's rule (contextual flags may fire citation-less)** — rejected: erodes the
  defensibility that distinguishes the tool from a generic LLM bias checker.
- **Allow model free-text citations** — rejected: fabricated citations are worse than none;
  a reference into a curated table is verifiable, a generated string is not.
