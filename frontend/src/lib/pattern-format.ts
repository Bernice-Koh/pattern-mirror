/** Shared presentation formatters for the Pattern Dashboard's pattern statements (#67, #68). */

import type { BiasCategory } from '@/lib/patterns-contract'

/** Title-case a category enum value: `family_status` → "Family status". */
export function categoryLabel(category: BiasCategory): string {
  const spaced = category.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** One significant figure is enough for a p-value pill; floor the vanishingly small. */
export function formatPValue(pValue: number): string {
  if (pValue < 0.0001) return '< 0.0001'
  return parseFloat(pValue.toPrecision(1)).toString()
}
