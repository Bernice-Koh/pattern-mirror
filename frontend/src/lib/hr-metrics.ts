/** Firm-wide figures the HR Portal derives from the effectiveness aggregate (#70 → #71). The
 *  aggregate carries per-cell adopted/total counts; the dashboards present them as a flag-volume
 *  trend, two share-of-flags breakdowns, and two headline rates. Pure functions, no I/O. */

import type { BiasCategory } from '@/lib/patterns-contract'
import type { DocType } from '@/lib/analyze-contract'
import type { EffectivenessReport } from '@/lib/hr-contract'

export interface VolumePoint {
  period: string
  flag_count: number
}

export interface CategoryShare {
  category: BiasCategory
  share: number
}

export interface DocTypeShare {
  doc_type: DocType
  share: number
}

/** Flags raised firm-wide per month — each period's total flag count, oldest first. */
export function flagVolumeOverTime(report: EffectivenessReport): VolumePoint[] {
  return report.adoption_over_time.map((cell) => ({
    period: cell.period,
    flag_count: cell.total_count,
  }))
}

/** The drop in monthly flag volume from the first month to the latest, as a 0–1 fraction.
 *  Null when there are fewer than two months or the first month carried no flags. */
export function flagVolumeDrop(report: EffectivenessReport): number | null {
  const series = report.adoption_over_time
  if (series.length < 2) return null
  const first = series[0].total_count
  const last = series[series.length - 1].total_count
  if (first === 0) return null
  return (first - last) / first
}

/** Firm-wide share of flags acted on before submission, as a 0–1 rate. Null when no flags. */
export function overallAdoptionRate(
  report: EffectivenessReport,
): number | null {
  const adopted = report.adoption_over_time.reduce(
    (sum, cell) => sum + cell.adopted_count,
    0,
  )
  const total = report.adoption_over_time.reduce(
    (sum, cell) => sum + cell.total_count,
    0,
  )
  return total === 0 ? null : adopted / total
}

/** Each document type's share of all firm-wide flags, as 0–1 fractions. */
export function shareByDocType(report: EffectivenessReport): DocTypeShare[] {
  const total = report.adoption_by_doc_type.reduce(
    (sum, cell) => sum + cell.total_count,
    0,
  )
  if (total === 0) return []
  return report.adoption_by_doc_type.map((cell) => ({
    doc_type: cell.doc_type,
    share: cell.total_count / total,
  }))
}

/** Each bias category's share of all firm-wide flags, as 0–1 fractions, largest first. */
export function shareByCategory(report: EffectivenessReport): CategoryShare[] {
  const total = report.adoption_by_category.reduce(
    (sum, cell) => sum + cell.total_count,
    0,
  )
  if (total === 0) return []
  return report.adoption_by_category
    .map((cell) => ({
      category: cell.category,
      share: cell.total_count / total,
    }))
    .sort((a, b) => b.share - a.share)
}
