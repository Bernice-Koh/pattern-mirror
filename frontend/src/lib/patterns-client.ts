/** Client for the /patterns read endpoint: the signed-in manager's gated, cached patterns (#66).
 *  Read-only — the statistics are done server-side; this just fetches them for the dashboard. */

import { apiFetch } from '@/lib/http'
import type { PatternReport } from '@/lib/patterns-contract'

/** A non-OK response from /patterns. Carries the status so callers can tell apart causes. */
export class PatternError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Patterns request failed with status ${status}`)
    this.name = 'PatternError'
    this.status = status
  }
}

/** Fetch the current manager's significant writing and decision patterns. */
export async function getPatterns(): Promise<PatternReport> {
  const response = await apiFetch('/patterns', { method: 'GET' })
  if (!response.ok) throw new PatternError(response.status)
  return (await response.json()) as PatternReport
}
