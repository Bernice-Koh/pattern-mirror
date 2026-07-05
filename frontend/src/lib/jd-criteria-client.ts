/** Client for the JD-criteria endpoints (#122): draft criteria from the JD text, read the
 *  confirmed set, and confirm the manager's edited set. Drafting is AI-assisted; only the
 *  confirmed set is persisted as the drift reference. */

import { apiFetch } from '@/lib/http'
import type {
  ConfirmJdCriteriaRequest,
  DraftJdCriteriaRequest,
  JdCriteriaResponse,
} from '@/lib/jd-criteria-contract'

/** A non-OK response from a JD-criteria call. Carries the status so callers can tell drafting
 *  being unavailable (503, no LLM key — fall back to manual entry) from a real failure. */
export class JdCriteriaError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`JD criteria request failed with status ${status}`)
    this.name = 'JdCriteriaError'
    this.status = status
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await apiFetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) throw new JdCriteriaError(response.status)
  return (await response.json()) as T
}

/** Read the JD's confirmed criteria, so the confirm step pre-fills an already-published set. */
export function getJdCriteria(documentId: string): Promise<JdCriteriaResponse> {
  return requestJson(`/documents/${documentId}/jd-criteria`, { method: 'GET' })
}

/** Draft criteria from the JD text with the extraction agent. Persists nothing; the manager
 *  reviews the result before confirming. Rejects with a 503 when no LLM client is configured. */
export function draftJdCriteria(
  documentId: string,
  body: DraftJdCriteriaRequest,
): Promise<JdCriteriaResponse> {
  return requestJson(`/documents/${documentId}/jd-criteria/draft`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** Confirm the manager's edited criteria as the JD's drift reference (idempotent replace). */
export function confirmJdCriteria(
  documentId: string,
  body: ConfirmJdCriteriaRequest,
): Promise<JdCriteriaResponse> {
  return requestJson(`/documents/${documentId}/jd-criteria`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}
