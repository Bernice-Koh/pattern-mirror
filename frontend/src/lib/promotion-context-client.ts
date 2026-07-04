/** Client for the promotion-context read: the rubric bar, context chips, and peer corroboration the
 *  Promotion Writeup shows above the editor. A promotion with no rubric still returns 200 with empty
 *  criteria. */

import { apiFetch } from '@/lib/http'
import type { PromotionContext } from '@/lib/promotion-context-contract'

/** Fetch a promotion document's rubric bar, context chips, and peer corroboration. */
export async function getPromotionContext(
  documentId: string,
): Promise<PromotionContext> {
  const response = await apiFetch(
    `/documents/${documentId}/promotion-context`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    },
  )
  if (!response.ok) {
    throw new Error(
      `Promotion context request failed with status ${response.status}`,
    )
  }
  return (await response.json()) as PromotionContext
}
