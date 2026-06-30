/** Composes a writing pattern's structured facts into card-ready presentation: a flat, factual
 *  sentence and its supporting ratio. No statistics and no editorialising happen here — the facts
 *  come gated from the backend (#66); this only states them plainly so the manager draws the
 *  conclusion (Mirror-not-Judge, design spec §2 View 3). */

import type { BiasCategory, WritingPattern } from '@/lib/patterns-contract'

/** Plural subject nouns for the gender groups the aggregator keys on; raw key is the fallback. */
const GROUP_NOUNS: Record<string, string> = {
  male: 'men',
  female: 'women',
}

export interface PatternStatement {
  /** "Gender · word choice" — category and the kind of pattern. */
  eyebrow: string
  /** Flat factual statement, e.g. `"sharp" appears in 6 documents — 5 about men, 1 about women.` */
  sentence: string
  /** Dominant group's share of supporting documents, 0–1, for the bar. */
  ratio: number
  /** "5 of 6 men" — the dominant group against the supporting total. */
  ratioLabel: string
  /** The p-value formatted for the pill, e.g. "0.0008". */
  pValueLabel: string
  /** Number of source documents — the citation count and drill-down target. */
  notesCount: number
}

function groupNoun(key: string): string {
  return GROUP_NOUNS[key] ?? key
}

/** Title-case a category enum value: `family_status` → "Family status". */
function categoryLabel(category: BiasCategory): string {
  const spaced = category.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** One significant figure is enough for a p-value pill; floor the vanishingly small. */
function formatPValue(pValue: number): string {
  if (pValue < 0.0001) return '< 0.0001'
  return parseFloat(pValue.toPrecision(1)).toString()
}

export function patternStatement(pattern: WritingPattern): PatternStatement {
  const groups = Object.entries(pattern.group_counts).sort(
    ([, a], [, b]) => b - a,
  )
  const [dominantKey, dominantCount] = groups[0]
  const minority = groups[1]
  const total = pattern.supporting_count

  const dominantNoun = groupNoun(dominantKey)
  const breakdown =
    !minority || minority[1] === 0
      ? `all ${total} about ${dominantNoun}`
      : `${dominantCount} about ${dominantNoun}, ${minority[1]} about ${groupNoun(minority[0])}`

  return {
    eyebrow: `${categoryLabel(pattern.category)} · word choice`,
    sentence: `"${pattern.term}" appears in ${total} documents — ${breakdown}.`,
    ratio: total === 0 ? 0 : dominantCount / total,
    ratioLabel: `${dominantCount} of ${total} ${dominantNoun}`,
    pValueLabel: formatPValue(pattern.p_value),
    notesCount: pattern.document_ids.length,
  }
}
