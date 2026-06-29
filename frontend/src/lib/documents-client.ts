/** Client for the /documents lifecycle: create a draft, restore it, autosave it, submit it.
 *  Autosave and submit are deliberately separate from the analysis path — saving text never
 *  triggers an engine run. */

import { apiFetch } from '@/lib/http'
import type {
  CreateDocumentRequest,
  DocumentResponse,
  SubmitRequest,
  UpdateDraftRequest,
} from '@/lib/documents-contract'

/** A non-OK response from a /documents call. Carries the status so callers can tell a
 *  missing draft (404, restore from a stale id) apart from a real failure. */
export class DocumentError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Document request failed with status ${status}`)
    this.name = 'DocumentError'
    this.status = status
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await apiFetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) throw new DocumentError(response.status)
  return (await response.json()) as T
}

/** Create an empty draft so the editor has a stable document to analyse and autosave against. */
export function createDocument(
  body: CreateDocumentRequest,
): Promise<DocumentResponse> {
  return requestJson('/documents', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** Fetch a document by id to restore its draft on load. Rejects with a 404 if it is gone. */
export function getDocument(documentId: string): Promise<DocumentResponse> {
  return requestJson(`/documents/${documentId}`, { method: 'GET' })
}

/** Persist an autosave of the draft's title and content. Runs no analysis. */
export function updateDraft(
  documentId: string,
  body: UpdateDraftRequest,
): Promise<DocumentResponse> {
  return requestJson(`/documents/${documentId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** Submit the draft, capturing the final text as the version adoption is measured against. */
export function submitDocument(
  documentId: string,
  body: SubmitRequest,
): Promise<DocumentResponse> {
  return requestJson(`/documents/${documentId}/submit`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
