/** Shared presentation formatters for the Pattern Dashboard's pattern statements (#67, #68, #99)
 *  and the HR Portal's trend dashboards (#71). */

import type { DocType } from '@/lib/analyze-contract'
import type { BiasCategory } from '@/lib/patterns-contract'

const DOC_TYPE_LABELS: Record<DocType, string> = {
  jd: 'Job descriptions',
  feedback: 'Interview feedback',
  promotion: 'Promotion writeups',
}

const MONTH_LABELS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

/** Title-case a category enum value: `family_status` → "Family status". */
export function categoryLabel(category: BiasCategory): string {
  const spaced = category.replaceAll('_', ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** A document type's plural, human-facing label: `feedback` → "Interview feedback". */
export function docTypeLabel(docType: DocType): string {
  return DOC_TYPE_LABELS[docType]
}

/** "2026-03" → "Mar"; the raw period is the fallback for an unexpected shape. */
export function periodLabel(period: string): string {
  const month = Number(period.split('-')[1])
  return MONTH_LABELS[month - 1] ?? period
}

/** The year, or year range, a set of "YYYY-MM" periods spans — shown once under a month axis. */
export function yearSpanLabel(periods: string[]): string {
  const years = periods.map((period) => period.split('-')[0])
  const first = years[0]
  const last = years.at(-1) ?? first
  return first === last ? first : `${first}–${last}`
}

/** One significant figure is enough for a p-value pill; floor the vanishingly small. */
export function formatPValue(pValue: number): string {
  if (pValue < 0.0001) return '< 0.0001'
  return Number.parseFloat(pValue.toPrecision(1)).toString()
}
