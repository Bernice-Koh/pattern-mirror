/** Client for the drift-findings API: read a document's coverage findings and record a
 *  dismiss/undo on one. Findings are read after the stream's `done` event, not streamed (#116). */

import { apiFetch } from '@/lib/http'
import type {
  DriftFinding,
  DriftInteractionKind,
  DriftInteractionResponse,
} from '@/lib/drift-contract'

/** A non-OK response from a drift call, carrying the status so callers can tell apart a missing
 *  document from a real failure. */
export class DriftError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Drift request failed with status ${status}`)
    this.name = 'DriftError'
    this.status = status
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await apiFetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) throw new DriftError(response.status)
  return (await response.json()) as T
}

/** List a document's latest-run, un-suppressed drift findings. */
export function listDriftFindings(documentId: string): Promise<DriftFinding[]> {
  return requestJson(`/documents/${documentId}/drift-findings`, {
    method: 'GET',
  })
}

/** Record a manager's dismiss/undo on a drift finding. */
export function recordDriftInteraction(
  findingId: string,
  kind: DriftInteractionKind,
): Promise<DriftInteractionResponse> {
  return requestJson(`/drift-findings/${findingId}/interactions`, {
    method: 'POST',
    body: JSON.stringify({ kind }),
  })
}
