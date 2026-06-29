/** Client for the flag-interactions endpoint: records a manager's accept/dismiss/undo on
 *  a flag and returns the persisted event. */

import { apiFetch } from '@/lib/http'
import type {
  InteractionRequest,
  InteractionResponse,
} from '@/lib/interaction-contract'

/** A non-OK response from the interactions endpoint. The status lets the caller decide
 *  whether to roll back the optimistic update. */
export class InteractionError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Interaction request failed with status ${status}`)
    this.name = 'InteractionError'
    this.status = status
  }
}

/** Record an interaction against a flag. */
export async function recordInteraction(
  flagId: string,
  request: InteractionRequest,
  signal?: AbortSignal,
): Promise<InteractionResponse> {
  const response = await apiFetch(`/flags/${flagId}/interactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) throw new InteractionError(response.status)
  return (await response.json()) as InteractionResponse
}
