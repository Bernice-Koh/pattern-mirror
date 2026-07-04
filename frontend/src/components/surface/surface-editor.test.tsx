import { createElement, createRef } from 'react'
import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CitedFlag } from '@/lib/analyze-contract'
import { analyzeDocument } from '@/lib/analyze-client'
import { listFlags } from '@/lib/flags-client'
import { SurfaceEditor, type SurfaceEditorHandle } from './surface-editor'
import { useFlagStream } from './use-flag-stream'
import { applyFlags } from './flag-decorations'

const FLAG: CitedFlag = {
  id: 'f1',
  source_stage: 'contextual',
  category: 'race',
  raw_span: 'young rockstar',
  start_offset: 0,
  end_offset: 14,
  explanation: 'Coded language.',
  citation: {
    source_type: 'tafep',
    title: 'TAFEP',
    reference: 'TAFEP-2024',
    publication_year: 2024,
    finding: null,
  },
  recommendations: {
    rationale: 'r',
    alternatives: ['team contribution', 'values fit'],
  },
}

const { insertContentAt, run, fakeEditor } = vi.hoisted(() => {
  const run = vi.fn()
  const insertContentAt = vi.fn(() => ({ run }))
  const focus = vi.fn(() => ({ insertContentAt }))
  return {
    run,
    insertContentAt,
    fakeEditor: {
      state: {
        doc: { content: { size: 100 }, textBetween: () => 'young rockstar' },
      },
      chain: () => ({ focus }),
      view: {},
      getText: () => '',
    },
  }
})

// EditorContent renders a flagged span so hover detection has a target to resolve.
vi.mock('@tiptap/react', () => ({
  useEditor: () => fakeEditor,
  EditorContent: () =>
    createElement(
      'span',
      { className: 'flag-context', 'data-flag-id': 'f1' },
      'young rockstar',
    ),
}))
vi.mock('@tiptap/starter-kit', () => ({ default: {} }))
vi.mock('@/components/surface/flag-decorations', () => ({
  applyFlags: vi.fn(),
  FlagDecorations: {},
}))
vi.mock('@/lib/analyze-client', () => ({ analyzeDocument: vi.fn() }))
vi.mock('@/lib/flags-client', () => ({ listFlags: vi.fn() }))
vi.mock('@/components/surface/use-flag-stream', () => ({
  useFlagStream: vi.fn(),
}))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

/** A reopened document seeds its panel from stored flags, then the live layers take over on the
 *  first edit or re-check. The mocked editor can't emit an edit, so re-check is how these tests
 *  hand the surface to the live layers (its contextual flags are the mocked `useFlagStream`). */
async function activateLive() {
  fireEvent.click(screen.getByRole('button', { name: 'Re-check' }))
  // Let the disabled hydration query settle so its resolution never lands outside act().
  await waitFor(() => expect(listFlags).toHaveBeenCalled())
}

describe('SurfaceEditor', () => {
  beforeEach(() => {
    insertContentAt.mockClear()
    run.mockClear()
    vi.mocked(applyFlags).mockClear()
    vi.mocked(analyzeDocument).mockReset()
    vi.mocked(listFlags).mockReset().mockResolvedValue([])
    vi.mocked(useFlagStream).mockReturnValue({
      contextualFlags: [FLAG],
      recheck: vi.fn(),
      isRechecking: false,
    })
  })

  it('applyRecommendation replaces the flagged span with the chosen phrasing', () => {
    const ref = createRef<SurfaceEditorHandle>()
    render(<SurfaceEditor ref={ref} documentId={null} initialContent="" />, {
      wrapper,
    })

    act(() => ref.current!.applyRecommendation(FLAG, 'team contribution'))

    expect(insertContentAt).toHaveBeenCalledWith(
      { from: 1, to: 15 },
      'team contribution',
    )
  })

  it('applyRecommendation is a no-op when the span no longer matches', () => {
    const ref = createRef<SurfaceEditorHandle>()
    render(<SurfaceEditor ref={ref} documentId={null} initialContent="" />, {
      wrapper,
    })

    act(() =>
      ref.current!.applyRecommendation({ ...FLAG, raw_span: 'stale' }, 'x'),
    )

    expect(insertContentAt).not.toHaveBeenCalled()
  })

  it('re-hydrates stored flags on open without running the live layers', async () => {
    vi.mocked(listFlags).mockResolvedValue([FLAG])
    const onFlagsChange = vi.fn()
    // Read-only stands in for a reopened submitted document: no editing, so no live run at all.
    render(
      <SurfaceEditor
        documentId="doc-1"
        editable={false}
        initialContent="saved text"
        onFlagsChange={onFlagsChange}
      />,
      { wrapper },
    )

    await waitFor(() => expect(onFlagsChange).toHaveBeenCalledWith([FLAG]))
    expect(listFlags).toHaveBeenCalledWith('doc-1')
    expect(analyzeDocument).not.toHaveBeenCalled()
  })

  it('does not run Layer 1 on open before the manager edits', async () => {
    render(<SurfaceEditor documentId="doc-1" initialContent="biased text" />, {
      wrapper,
    })

    await waitFor(() => expect(listFlags).toHaveBeenCalledWith('doc-1'))
    expect(analyzeDocument).not.toHaveBeenCalled()
  })

  it('runs Layer 1 analysis once the surface goes live', async () => {
    vi.mocked(analyzeDocument).mockResolvedValue({
      document_id: 'doc-1',
      analysis_run_id: 'run-1',
      content_hash: 'hash',
      flags: [],
    })
    render(<SurfaceEditor documentId="doc-1" initialContent="biased text" />, {
      wrapper,
    })

    await activateLive()

    await waitFor(() =>
      expect(analyzeDocument).toHaveBeenCalledWith(
        { document_id: 'doc-1', content: 'biased text' },
        expect.anything(),
      ),
    )
  })

  it('reveals the recommendation popover when a flagged span is hovered', async () => {
    const onApplyRecommendation = vi.fn()
    render(
      <SurfaceEditor
        documentId="doc-1"
        initialContent=""
        onApplyRecommendation={onApplyRecommendation}
      />,
      { wrapper },
    )
    await activateLive()

    fireEvent.mouseOver(screen.getByText('young rockstar'))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'team contribution' }))
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApplyRecommendation).toHaveBeenCalledWith(
      FLAG,
      'team contribution',
    )
  })

  it('dismisses the flag from the popover', async () => {
    const onDismissFlag = vi.fn()
    render(
      <SurfaceEditor
        documentId="doc-1"
        initialContent=""
        onDismissFlag={onDismissFlag}
      />,
      { wrapper },
    )
    await activateLive()

    fireEvent.mouseOver(screen.getByText('young rockstar'))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss flag' }))

    expect(onDismissFlag).toHaveBeenCalledWith(FLAG)
  })

  it('clears a dismissed flag from the inline decorations', async () => {
    render(
      <SurfaceEditor
        documentId="doc-1"
        initialContent=""
        resolvedFlagIds={new Set(['f1'])}
      />,
      { wrapper },
    )
    await activateLive()

    // FLAG is the only flag and is dismissed, so the editor decorates nothing.
    const lastCall = vi.mocked(applyFlags).mock.calls.at(-1)?.[1] as CitedFlag[]
    expect(lastCall).toEqual([])
  })

  it('does not open a popover for a dismissed flag on hover', async () => {
    render(
      <SurfaceEditor
        documentId="doc-1"
        initialContent=""
        resolvedFlagIds={new Set(['f1'])}
      />,
      { wrapper },
    )
    await activateLive()

    fireEvent.mouseOver(screen.getByText('young rockstar'))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('hides the Re-check control when opened read-only', () => {
    render(
      <SurfaceEditor
        documentId="doc-1"
        editable={false}
        initialContent="saved text"
      />,
      { wrapper },
    )

    expect(screen.queryByRole('button', { name: /re-check/i })).toBeNull()
  })

  it('disables the Re-check button until a document exists', () => {
    render(<SurfaceEditor documentId={null} initialContent="" />, { wrapper })

    expect(screen.getByRole('button', { name: /re-check/i })).toBeDisabled()
  })

  it('shows a re-check in progress on the button', () => {
    vi.mocked(useFlagStream).mockReturnValue({
      contextualFlags: [FLAG],
      recheck: vi.fn(),
      isRechecking: true,
    })
    render(<SurfaceEditor documentId={null} initialContent="" />, { wrapper })

    expect(screen.getByRole('button', { name: /re-checking/i })).toBeDisabled()
  })

  it('schedules a close when the pointer leaves the flag, and reopens on re-hover', async () => {
    render(<SurfaceEditor documentId="doc-1" initialContent="" />, { wrapper })
    await activateLive()
    const span = screen.getByText('young rockstar')

    fireEvent.mouseOver(span)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // Moving onto non-flag content schedules a close; re-hovering cancels it.
    fireEvent.mouseOver(span.parentElement!)
    fireEvent.mouseLeave(span.parentElement!)
    fireEvent.mouseOver(span)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})
