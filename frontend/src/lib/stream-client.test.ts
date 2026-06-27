import { describe, it, expect, afterEach, vi } from 'vitest'
import { streamAnalysis, StreamError } from './stream-client'
import type { AnalyzeStreamRequest, StreamEvent } from './stream-contract'
import type { CitedFlag } from './analyze-contract'

const REQUEST: AnalyzeStreamRequest = {
  document_id: 'doc-1',
  content: 'an aggressive leader',
}

const FLAG: CitedFlag = {
  id: 'flag-1',
  source_stage: 'contextual',
  category: 'gender',
  raw_span: 'aggressive',
  start_offset: 3,
  end_offset: 13,
  explanation: 'Gender-coded leadership language.',
  citation: {
    source_type: 'tafep',
    title: 'TAFEP Guidelines',
    reference: 'TAFEP-2024',
    publication_year: 2024,
    finding: null,
  },
}

function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

/** A fake Response whose body streams the given strings as byte chunks, so frame
 *  boundaries can be placed anywhere relative to chunk boundaries. */
function streamResponse(chunks: string[], ok = true): Response {
  const encoder = new TextEncoder()
  const queue = chunks.map((chunk) => encoder.encode(chunk))
  let i = 0
  const reader = {
    read: () =>
      Promise.resolve(
        i < queue.length
          ? { done: false, value: queue[i++] }
          : { done: true, value: undefined },
      ),
  }
  return { ok, body: { getReader: () => reader } } as unknown as Response
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

async function collect(request: AnalyzeStreamRequest): Promise<StreamEvent[]> {
  const events: StreamEvent[] = []
  for await (const event of streamAnalysis(request)) events.push(event)
  return events
}

describe('streamAnalysis', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('parses stage, flag, and done events into typed shapes', async () => {
    mockFetch(
      streamResponse([
        frame('stage', { stage: 'contextual' }),
        frame('flag', FLAG),
        frame('done', {
          analysis_run_id: 'run-1',
          status: 'complete',
          flag_count: 1,
        }),
      ]),
    )

    await expect(collect(REQUEST)).resolves.toEqual([
      { type: 'stage', stage: 'contextual' },
      { type: 'flag', flag: FLAG },
      {
        type: 'done',
        analysis_run_id: 'run-1',
        status: 'complete',
        flag_count: 1,
      },
    ])
  })

  it('reassembles a frame split across two chunks', async () => {
    const whole = frame('flag', FLAG)
    const split = Math.floor(whole.length / 2)
    mockFetch(streamResponse([whole.slice(0, split), whole.slice(split)]))

    await expect(collect(REQUEST)).resolves.toEqual([
      { type: 'flag', flag: FLAG },
    ])
  })

  it('emits both events when one chunk carries two frames', async () => {
    mockFetch(
      streamResponse([
        frame('stage', { stage: 'dictionary' }) +
          frame('stage', { stage: 'contextual' }),
      ]),
    )

    await expect(collect(REQUEST)).resolves.toEqual([
      { type: 'stage', stage: 'dictionary' },
      { type: 'stage', stage: 'contextual' },
    ])
  })

  it('skips an unrecognised event type', async () => {
    mockFetch(
      streamResponse([
        frame('heartbeat', { t: 1 }),
        frame('stage', { stage: 'judge' }),
      ]),
    )

    await expect(collect(REQUEST)).resolves.toEqual([
      { type: 'stage', stage: 'judge' },
    ])
  })

  it('throws StreamError carrying the status on a non-OK response', async () => {
    mockFetch(streamResponse([], false))

    await expect(collect(REQUEST)).rejects.toBeInstanceOf(StreamError)
  })

  it('forwards an abort signal to fetch', async () => {
    const fetchSpy = mockFetch(streamResponse([]))
    const controller = new AbortController()

    for await (const _event of streamAnalysis(REQUEST, controller.signal)) {
      void _event
    }

    expect(fetchSpy).toHaveBeenCalledWith(
      '/analyze/stream',
      expect.objectContaining({ signal: controller.signal }),
    )
  })
})
