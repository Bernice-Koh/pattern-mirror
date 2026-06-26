/** Event types for the /analyze/stream endpoint: Layer 2 of JD Studio's two-trigger
 *  model. The backend emits Server-Sent Events as each engine stage completes; these
 *  are the parsed, typed shapes the client yields. The flag payload reuses the Layer-1
 *  CitedFlag so both layers render through one decoration path. */

import type { CitedFlag } from '@/lib/analyze-contract'

/** A pipeline stage finished — progress, even when it surfaced no flags. */
export interface StageEvent {
  type: 'stage'
  stage: string
}

/** One verified flag the client should render as it arrives. */
export interface FlagEvent {
  type: 'flag'
  flag: CitedFlag
}

/** The terminal event: the run is done, superseded, or failed. Always emitted last. */
export interface DoneEvent {
  type: 'done'
  analysis_run_id: string
  status: string
  flag_count: number
}

export type StreamEvent = StageEvent | FlagEvent | DoneEvent

export interface AnalyzeStreamRequest {
  document_id: string
  content: string
}
