/** Client for the /analyze/stream endpoint: Layer 2 of JD Studio's two-trigger model.
 *  POSTs the document's current text and yields the engine's flags as each stage
 *  completes, parsed from Server-Sent Events. The transport is POST (not native
 *  EventSource) so the text rides in the body and an AbortSignal cancels the stream
 *  when the manager resumes typing. */

import { API_BASE_URL } from '@/lib/api'
import type { CitedFlag } from '@/lib/analyze-contract'
import type { AnalyzeStreamRequest, StreamEvent } from '@/lib/stream-contract'

const FRAME_SEPARATOR = '\n\n'

/** A non-OK response from /analyze/stream. Carries the status so the caller can
 *  decide whether to retry; the editor treats any failure as "keep the last flags". */
export class StreamError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Analyze stream failed with status ${status}`)
    this.name = 'StreamError'
    this.status = status
  }
}

/** Parse one SSE frame (its ``event:``/``data:`` lines) into a typed event.
 *  Returns null for a frame with no data or an unrecognised event name, so an
 *  unknown future event type is skipped rather than breaking the stream. */
function parseFrame(raw: string): StreamEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice('event:'.length).trim()
    else if (line.startsWith('data:'))
      dataLines.push(line.slice('data:'.length).trim())
  }
  if (dataLines.length === 0) return null

  const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
  switch (event) {
    case 'stage':
      return { type: 'stage', stage: data.stage as string }
    case 'flag':
      return { type: 'flag', flag: data as unknown as CitedFlag }
    case 'done':
      return {
        type: 'done',
        analysis_run_id: data.analysis_run_id as string,
        status: data.status as string,
        flag_count: data.flag_count as number,
      }
    default:
      return null
  }
}

/** Run the full engine over the document and yield each flag as its stage verifies it.
 *  `signal` aborts the in-flight stream so a resumed keystroke cancels a stale run;
 *  the rejection it raises (an AbortError) is the caller's signal to stop, not an error.
 *
 *  Throws StreamError on a non-OK response. */
export async function* streamAnalysis(
  request: AnalyzeStreamRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const response = await fetch(`${API_BASE_URL}/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
    signal,
  })
  if (!response.ok) throw new StreamError(response.status)
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let separator = buffer.indexOf(FRAME_SEPARATOR)
    while (separator !== -1) {
      const frame = buffer.slice(0, separator)
      buffer = buffer.slice(separator + FRAME_SEPARATOR.length)
      const event = parseFrame(frame)
      if (event) yield event
      separator = buffer.indexOf(FRAME_SEPARATOR)
    }
  }

  const tail = parseFrame(buffer)
  if (tail) yield tail
}
