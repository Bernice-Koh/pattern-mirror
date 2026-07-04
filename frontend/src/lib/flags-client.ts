/** Client for the stored-flags API: read a document's latest-run, surfaced bias flags so a
 *  reopened surface re-hydrates them without a fresh engine run. Read once on open; the live
 *  `/analyze` + `/analyze/stream` paths take over only once the manager edits (#130). */

import { apiFetch } from '@/lib/http'
import type { CitedFlag } from '@/lib/analyze-contract'

/** A non-OK response from a stored-flags call, carrying the status so the editor can tell a missing
 *  document from a real failure and fall back to showing no flags. */
export class FlagsError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Stored-flags request failed with status ${status}`)
    this.name = 'FlagsError'
    this.status = status
  }
}

/** List a document's latest-run, un-suppressed flags for re-hydration on reopen. */
export async function listFlags(documentId: string): Promise<CitedFlag[]> {
  const response = await apiFetch(`/documents/${documentId}/flags`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) throw new FlagsError(response.status)
  return (await response.json()) as CitedFlag[]
}
