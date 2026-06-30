/** Composes a decision pattern's structured facts into card-ready presentation: a flat, factual
 *  sentence and its adoption ratio. No statistics and no editorialising happen here — the facts
 *  come gated from the backend (#66); this only states them plainly so the manager draws the
 *  conclusion (Mirror-not-Judge, design spec §2 View 3 Layer 2, §13). */

import type { DecisionPattern } from '@/lib/patterns-contract'
import { categoryLabel, formatPValue } from '@/lib/pattern-format'

export interface DecisionStatement {
  /** "Gender · your decisions" — category and that this is a behavioural pattern. */
  eyebrow: string
  /** Flat factual statement, e.g. `You revised flagged gender language in 2 of 9 cases.` */
  sentence: string
  /** Adoption rate, 0–1, for the bar — the §13 headline metric. */
  rate: number
  /** "2 of 9 revised" — the adopted count against the total decided. */
  rateLabel: string
  /** The p-value formatted for the pill, e.g. "0.01". */
  pValueLabel: string
  /** Number of source documents — the citation count and drill-down target. */
  notesCount: number
}

export function decisionStatement(pattern: DecisionPattern): DecisionStatement {
  const category = categoryLabel(pattern.category).toLowerCase()
  return {
    eyebrow: `${categoryLabel(pattern.category)} · your decisions`,
    sentence: `You revised flagged ${category} language in ${pattern.adopted_count} of ${pattern.total_count} flagged cases.`,
    rate: pattern.adoption_rate,
    rateLabel: `${pattern.adopted_count} of ${pattern.total_count} revised`,
    pValueLabel: formatPValue(pattern.p_value),
    notesCount: pattern.document_ids.length,
  }
}
