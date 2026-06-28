import { createElement, createRef } from 'react'
import type { ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { CitedFlag } from '@/lib/analyze-contract'
import { JdEditor, type JdEditorHandle } from './jd-editor'

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
vi.mock('@/components/jd-studio/flag-decorations', () => ({
  applyFlags: vi.fn(),
  FlagDecorations: {},
}))
vi.mock('@/lib/analyze-client', () => ({ analyzeDocument: vi.fn() }))
vi.mock('@/components/jd-studio/use-flag-stream', () => ({
  useFlagStream: () => [FLAG],
}))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient()
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('JdEditor', () => {
  beforeEach(() => {
    insertContentAt.mockClear()
    run.mockClear()
  })

  it('applyRecommendation replaces the flagged span with the chosen phrasing', () => {
    const ref = createRef<JdEditorHandle>()
    render(<JdEditor ref={ref} docType="jd" initialContent="" />, { wrapper })

    act(() => ref.current!.applyRecommendation(FLAG, 'team contribution'))

    expect(insertContentAt).toHaveBeenCalledWith(
      { from: 1, to: 15 },
      'team contribution',
    )
  })

  it('applyRecommendation is a no-op when the span no longer matches', () => {
    const ref = createRef<JdEditorHandle>()
    render(<JdEditor ref={ref} docType="jd" initialContent="" />, { wrapper })

    act(() =>
      ref.current!.applyRecommendation({ ...FLAG, raw_span: 'stale' }, 'x'),
    )

    expect(insertContentAt).not.toHaveBeenCalled()
  })

  it('reveals the recommendation popover when a flagged span is hovered', () => {
    const onApplyRecommendation = vi.fn()
    render(
      <JdEditor
        docType="jd"
        initialContent=""
        onApplyRecommendation={onApplyRecommendation}
      />,
      { wrapper },
    )

    fireEvent.mouseOver(screen.getByText('young rockstar'))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'team contribution' }))
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApplyRecommendation).toHaveBeenCalledWith(
      FLAG,
      'team contribution',
    )
  })

  it('dismisses the flag from the popover', () => {
    const onDismissFlag = vi.fn()
    render(
      <JdEditor docType="jd" initialContent="" onDismissFlag={onDismissFlag} />,
      { wrapper },
    )

    fireEvent.mouseOver(screen.getByText('young rockstar'))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss flag' }))

    expect(onDismissFlag).toHaveBeenCalledWith(FLAG)
  })

  it('schedules a close when the pointer leaves the flag, and reopens on re-hover', () => {
    render(<JdEditor docType="jd" initialContent="" />, { wrapper })
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
