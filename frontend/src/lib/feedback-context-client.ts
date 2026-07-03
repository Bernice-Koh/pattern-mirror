/** Client for the feedback-context read: the criteria bar and context chips the Feedback
 *  Checkpoint shows above the editor. An unlinked feedback still returns 200 with empty criteria. */

import { apiFetch } from '@/lib/http'
import type { FeedbackContext } from '@/lib/feedback-context-contract'

/** Fetch a feedback document's criteria bar + context chips. */
export async function getFeedbackContext(
  documentId: string,
): Promise<FeedbackContext> {
  const response = await apiFetch(`/documents/${documentId}/feedback-context`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!response.ok) {
    throw new Error(
      `Feedback context request failed with status ${response.status}`,
    )
  }
  return (await response.json()) as FeedbackContext
}
