import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import type { CitedFlag, FlagSourceStage } from '@/lib/analyze-contract'
import type { StreamEvent } from '@/lib/stream-contract'
import { recheckAnalysis, streamAnalysis } from '@/lib/stream-client'
import { useFlagStream } from './use-flag-stream'

const STREAM_IDLE_MS = 3000

let streamEvents: StreamEvent[] = []
let recheckEvents: StreamEvent[] = []
let keepOpen = false
const capturedSignals: (AbortSignal | undefined)[] = []
const recheckSignals: (AbortSignal | undefined)[] = []

vi.mock('@/lib/stream-client', () => ({
  streamAnalysis: vi.fn(async function* (
    _request: unknown,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    capturedSignals.push(signal)
    for (const event of streamEvents) yield event
    // Park an in-flight run so abort-on-resume is observable.
    if (keepOpen) await new Promise<void>(() => {})
  }),
  recheckAnalysis: vi.fn(async function* (
    _documentId: string,
    _content: string,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    recheckSignals.push(signal)
    for (const event of recheckEvents) yield event
  }),
}))

const CITATION: CitedFlag['citation'] = {
  source_type: 'tafep',
  title: 'TAFEP Guidelines',
  reference: 'TAFEP-2024',
  publication_year: 2024,
  finding: null,
}

function flagEvent(id: string, source_stage: FlagSourceStage): StreamEvent {
  return {
    type: 'flag',
    flag: {
      id,
      source_stage,
      category: 'gender',
      raw_span: id,
      start_offset: 0,
      end_offset: 1,
      explanation: '',
      citation: CITATION,
    },
  }
}

/** Advance fake timers and flush the stream's microtasks together. */
async function idle(ms = STREAM_IDLE_MS): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

/** Drain the manual re-check stream's microtasks (no real delay to advance). */
async function flush(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0)
  })
}

describe('useFlagStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    streamEvents = []
    recheckEvents = []
    keepOpen = false
    capturedSignals.length = 0
    recheckSignals.length = 0
    vi.mocked(streamAnalysis).mockClear()
    vi.mocked(recheckAnalysis).mockClear()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('accumulates contextual flags and ignores dictionary flags from the stream', async () => {
    streamEvents = [
      { type: 'stage', stage: 'contextual' },
      flagEvent('ctx-1', 'contextual'),
      flagEvent('dict-1', 'dictionary'),
      {
        type: 'done',
        analysis_run_id: 'run-1',
        status: 'complete',
        flag_count: 2,
      },
    ]
    const { result, rerender } = renderHook(
      ({ t }) => useFlagStream('doc-1', t),
      {
        initialProps: { t: '' },
      },
    )

    act(() => rerender({ t: 'an aggressive leader' }))
    await idle()

    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-1'])
  })

  it('does not open a stream until the idle delay elapses', async () => {
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { rerender } = renderHook(({ t }) => useFlagStream('doc-1', t), {
      initialProps: { t: '' },
    })

    act(() => rerender({ t: 'hello' }))
    await idle(STREAM_IDLE_MS - 1)
    expect(streamAnalysis).not.toHaveBeenCalled()

    await idle(1)
    expect(streamAnalysis).toHaveBeenCalledOnce()
  })

  it('does not open a stream without a document id', async () => {
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { rerender } = renderHook(({ t }) => useFlagStream(null, t), {
      initialProps: { t: '' },
    })

    act(() => rerender({ t: 'hello' }))
    await idle()

    expect(streamAnalysis).not.toHaveBeenCalled()
  })

  it('aborts the in-flight stream when typing resumes', async () => {
    keepOpen = true
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { rerender } = renderHook(({ t }) => useFlagStream('doc-1', t), {
      initialProps: { t: '' },
    })

    act(() => rerender({ t: 'hello' }))
    await idle()
    const signal = capturedSignals[0]
    expect(signal?.aborted).toBe(false)

    act(() => rerender({ t: 'hello world' }))
    expect(signal?.aborted).toBe(true)
  })

  it('replaces the prior run’s flags when the next pause starts a new run', async () => {
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { result, rerender } = renderHook(
      ({ t }) => useFlagStream('doc-1', t),
      {
        initialProps: { t: '' },
      },
    )

    act(() => rerender({ t: 'first' }))
    await idle()
    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-1'])

    streamEvents = [flagEvent('ctx-2', 'contextual')]
    act(() => rerender({ t: 'second' }))
    await idle()

    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-2'])
  })

  it('keeps the prior run’s flags painted while a re-run is still in flight', async () => {
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { result, rerender } = renderHook(
      ({ t }) => useFlagStream('doc-1', t),
      {
        initialProps: { t: '' },
      },
    )

    act(() => rerender({ t: 'first' }))
    await idle()
    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-1'])

    // The re-run (as an accepted-flag edit would trigger) opens but yields nothing yet.
    keepOpen = true
    streamEvents = []
    act(() => rerender({ t: 'second' }))
    await idle()

    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-1'])
  })

  it('clears the prior run’s flags when a completed run finds none', async () => {
    streamEvents = [flagEvent('ctx-1', 'contextual')]
    const { result, rerender } = renderHook(
      ({ t }) => useFlagStream('doc-1', t),
      {
        initialProps: { t: '' },
      },
    )

    act(() => rerender({ t: 'first' }))
    await idle()
    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-1'])

    streamEvents = [
      { type: 'done', analysis_run_id: 'r', status: 'complete', flag_count: 0 },
    ]
    act(() => rerender({ t: 'second' }))
    await idle()

    expect(result.current.contextualFlags).toEqual([])
  })

  it('re-check runs the recheck stream into the same contextual accumulator', async () => {
    recheckEvents = [
      flagEvent('dict-1', 'dictionary'),
      flagEvent('ctx-9', 'contextual'),
      { type: 'done', analysis_run_id: 'r', status: 'complete', flag_count: 2 },
    ]
    const { result } = renderHook(() => useFlagStream('doc-1', 'text'))

    act(() => result.current.recheck())
    await flush()

    // Dictionary flags are ignored here (Layer 1 renders those); contextual ones surface.
    expect(result.current.contextualFlags.map((f) => f.id)).toEqual(['ctx-9'])
    expect(result.current.isRechecking).toBe(false)
    expect(recheckAnalysis).toHaveBeenCalledOnce()
  })

  it('re-check does nothing without a document id', async () => {
    recheckEvents = [flagEvent('ctx-9', 'contextual')]
    const { result } = renderHook(() => useFlagStream(null, 'text'))

    act(() => result.current.recheck())
    await flush()

    expect(recheckAnalysis).not.toHaveBeenCalled()
    expect(result.current.contextualFlags).toEqual([])
  })
})
