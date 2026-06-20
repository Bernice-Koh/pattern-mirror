/** Client for the /analyze endpoint. Returns an empty result until the engine
 *  is wired in. */

import type { AnalyzeRequest, AnalyzeResponse } from '@/lib/analyze-contract'

export async function analyzeDocument(
  request: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  void request // TODO: POST to the live /analyze endpoint.
  return {
    document_id: '',
    analysis_run_id: '',
    content_hash: '',
    flags: [],
  }
}
