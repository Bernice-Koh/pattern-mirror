/** Client for the /analyze endpoint: Layer 1 of JD Studio's two-trigger model.
 *  POSTs the document text and returns the persisted, cited dictionary flags. */

import { API_BASE_URL } from '@/lib/api'
import type { AnalyzeRequest, AnalyzeResponse } from '@/lib/analyze-contract'

/** A non-OK response from /analyze. Surfacing the status lets the caller decide
 *  whether to retry; the editor treats any failure as "keep the last flags". */
export class AnalyzeError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Analyze request failed with status ${status}`)
    this.name = 'AnalyzeError'
    this.status = status
  }
}

/** Run Stage 1 over the given text. `signal` lets a superseded keystroke abort
 *  its in-flight request so only the latest pass resolves. */
export async function analyzeDocument(
  request: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) throw new AnalyzeError(response.status)
  return (await response.json()) as AnalyzeResponse
}
