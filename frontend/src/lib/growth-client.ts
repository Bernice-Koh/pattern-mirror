/** Client for the dictionary-growth endpoints the HR review queue (#72) calls: list the pending
 *  additions, reconstruct one proposal's audit chain (#91), and record an approve/reject/defer
 *  decision (#90). All are HR-gated server-side; this just fetches and posts through apiFetch. */

import { apiFetch } from '@/lib/http'
import type {
  GrowthDecision,
  PendingAddition,
  ProposalAudit,
} from '@/lib/growth-contract'

/** A non-OK response from a /growth endpoint. Carries the status so callers can tell 409
 *  (already decided by another reviewer) apart from auth or server failures. */
export class GrowthError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Growth request failed with status ${status}`)
    this.name = 'GrowthError'
    this.status = status
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path, { method: 'GET' })
  if (!response.ok) throw new GrowthError(response.status)
  return (await response.json()) as T
}

/** The additions still open to a decision (pending or deferred), oldest first. */
export function getPendingAdditions(): Promise<PendingAddition[]> {
  return getJson<PendingAddition[]>('/growth/pending-additions')
}

/** The full provenance chain for one proposal: agent arguments, citation, decision, live row. */
export function getProposalAudit(proposalId: string): Promise<ProposalAudit> {
  return getJson<ProposalAudit>(`/growth/proposals/${proposalId}/audit`)
}

/** Record HR's decision on a queued addition. The response body differs by action, so this
 *  resolves to void — callers refetch the queue rather than read it. */
export async function decideAddition(
  additionId: string,
  decision: GrowthDecision,
): Promise<void> {
  const response = await apiFetch(
    `/growth/pending-additions/${additionId}/${decision}`,
    { method: 'POST' },
  )
  if (!response.ok) throw new GrowthError(response.status)
}
