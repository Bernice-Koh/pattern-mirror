/** Deriving the Promotion Writeup's rubric coverage and "what peers say" synthesis from the live
 *  drift findings (writeup vs rubric) and the static peer corroboration (§8). Pure functions, no
 *  LLM: the peer synthesis is a deterministic reading of the reference + the unevidenced criteria,
 *  anchored on the canonical rubric so a finding's wording never has to match a corroboration's. */

import type { CoverageItem } from '@/components/ui/coverage-list'
import type { DriftFinding } from '@/lib/drift-contract'
import type { PeerCorroboration } from '@/lib/promotion-context-contract'

export interface PeerSynthesis {
  lead: string
  synthesis: string
}

// A finding's criterion comes from the model reading the rubric, so match on a normalised key
// rather than exact text; the rubric list is the canonical anchor for both findings and peers.
function normalise(text: string): string {
  return text.toLowerCase().replace(/\s+/g, ' ').trim()
}

// Quote each criterion so the long rubric phrases read as distinct items rather than running
// together in the sentence.
function formatList(items: string[]): string {
  const quoted = items.map((item) => `“${item}”`)
  if (quoted.length === 1) return quoted[0]
  if (quoted.length === 2) return `${quoted[0]} and ${quoted[1]}`
  return `${quoted.slice(0, -1).join(', ')}, and ${quoted[quoted.length - 1]}`
}

/** Build one coverage row per rubric criterion: whether the writeup evidences it (live drift) and
 *  whether peers corroborate it (static). Before the first run the writeup side reads "not yet
 *  checked"; the peer signal is known from context and shows immediately. */
export function buildRubricCoverage(
  criteria: string[],
  findings: DriftFinding[],
  corroboration: PeerCorroboration[],
): CoverageItem[] {
  const addressedByCriterion = new Map(
    findings.map((finding) => [
      normalise(finding.criterion),
      finding.addressed,
    ]),
  )
  const corroboratedByCriterion = new Map(
    corroboration.map((entry) => [
      normalise(entry.criterion),
      entry.corroborated,
    ]),
  )
  const hasRun = findings.length > 0
  return criteria.map((criterion) => {
    const key = normalise(criterion)
    const addressed = addressedByCriterion.get(key) ?? false
    const corroborated = corroboratedByCriterion.get(key)
    return {
      label: criterion,
      addressed,
      statusLabel: hasRun
        ? addressed
          ? 'evidenced'
          : 'not evidenced'
        : 'not yet checked',
      corroboration:
        corroborated === undefined
          ? undefined
          : {
              corroborated,
              label: corroborated ? 'peers agree' : 'peers differ',
            },
    }
  })
}

/** Derive the "what peers say" panel from the peer corroboration and the live findings. Returns null
 *  when peers evidence nothing. After a run, the takeaway names the criteria peers back that the
 *  writeup has not yet evidenced — the gap that is the panel's whole point. */
export function derivePeerSynthesis(
  findings: DriftFinding[],
  corroboration: PeerCorroboration[],
): PeerSynthesis | null {
  const corroborated = corroboration
    .filter((entry) => entry.corroborated)
    .map((entry) => entry.criterion)
  if (corroborated.length === 0) return null

  const lead = `Peers evidence ${formatList(corroborated)}.`
  if (findings.length === 0) {
    return {
      lead,
      synthesis:
        'Run a check to see which of these your writeup already evidences.',
    }
  }

  const addressed = new Set(
    findings
      .filter((finding) => finding.addressed)
      .map((finding) => normalise(finding.criterion)),
  )
  const gap = corroborated.filter(
    (criterion) => !addressed.has(normalise(criterion)),
  )
  if (gap.length === 0) {
    return {
      lead,
      synthesis: 'Your writeup already evidences what peers consistently say.',
    }
  }
  return {
    lead,
    synthesis:
      `Your writeup doesn’t yet evidence ${formatList(gap)} — the criteria your peers ` +
      'point to most. The strongest evidence for this promotion may be in your peers’ ' +
      'words, not yet in yours.',
  }
}
