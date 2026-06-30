/** Client for the HR Portal's /hr read endpoints: firm-wide aggregate trends (#70 → #71).
 *  Read-only — the aggregation and small-cell suppression happen server-side; this just fetches. */

import { apiFetch } from '@/lib/http'
import type {
  DictionaryHealthReport,
  EffectivenessReport,
} from '@/lib/hr-contract'

/** A non-OK response from an /hr endpoint. Carries the status so callers can tell apart causes. */
export class HrError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`HR request failed with status ${status}`)
    this.name = 'HrError'
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path, { method: 'GET' })
  if (!response.ok) throw new HrError(response.status)
  return (await response.json()) as T
}

/** Firm-wide adoption trends: over time, by category, by document type. */
export function getEffectiveness(): Promise<EffectivenessReport> {
  return getJson<EffectivenessReport>('/hr/effectiveness')
}

/** Dictionary-growth health metrics; all-null until Dictionary Growth (#8) lands. */
export function getDictionaryHealth(): Promise<DictionaryHealthReport> {
  return getJson<DictionaryHealthReport>('/hr/dictionary-health')
}
