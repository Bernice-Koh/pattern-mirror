import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { recordInteraction } from '@/lib/interaction-client'
import { JdStudio } from './jd-studio'

// This suite renders JdStudio outside a router; it exercises flag interactions, not the
// document-open search param (#69), so the search reads as empty.
vi.mock('@tanstack/react-router', () => ({
  useSearch: () => ({}),
}))

const FLAG = vi.hoisted(() => ({
  id: 'f1',
  source_stage: 'contextual' as const,
  category: 'race' as const,
  raw_span: 'young rockstar',
  start_offset: 0,
  end_offset: 14,
  explanation: 'Coded language.',
  citation: {
    source_type: 'tafep' as const,
    title: 'TAFEP',
    reference: 'TAFEP-2024',
    publication_year: 2024,
    finding: null,
  },
  recommendations: {
    rationale: 'r',
    alternatives: ['team contribution', 'values fit'],
  },
}))

vi.mock('@/lib/interaction-client', () => ({
  recordInteraction: vi.fn().mockResolvedValue({
    id: 'i',
    flag_id: 'f1',
    kind: 'accept',
    dismissed: false,
  }),
}))

// Stub the TipTap editor: surface FLAG to the panel and expose a no-op apply handle.
vi.mock('@/components/jd-studio/jd-editor', async () => {
  const React = await import('react')
  return {
    JdEditor: React.forwardRef(function MockEditor(
      props: {
        onFlagsChange?: (flags: unknown[]) => void
        resolvedFlagIds?: ReadonlySet<string>
      },
      ref,
    ) {
      React.useImperativeHandle(ref, () => ({ applyRecommendation: vi.fn() }))
      const onFlagsChange = props.onFlagsChange
      React.useEffect(() => onFlagsChange?.([FLAG]), [onFlagsChange])
      // Surface the resolved-id set so the panel↔editor wiring is assertable.
      return React.createElement('div', {
        'data-testid': 'resolved-ids',
        'data-ids': [...(props.resolvedFlagIds ?? [])].join(','),
      })
    }),
  }
})

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('JdStudio', () => {
  it('logs an accept and removes the card when Apply is clicked', async () => {
    render(<JdStudio />, { wrapper })
    expect(screen.getByText('young rockstar')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    await waitFor(() =>
      expect(recordInteraction).toHaveBeenCalledWith(
        'f1',
        expect.objectContaining({
          kind: 'accept',
          accepted_alternative: 'team contribution',
        }),
      ),
    )
    await waitFor(() => expect(screen.queryByText('young rockstar')).toBeNull())
  })

  it('marks an applied flag resolved so its underline clears at once', async () => {
    render(<JdStudio />, { wrapper })
    expect(screen.getByTestId('resolved-ids')).toHaveAttribute('data-ids', '')

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    // Resolved before the re-scan returns, so the editor drops the underline immediately.
    await waitFor(() =>
      expect(screen.getByTestId('resolved-ids')).toHaveAttribute(
        'data-ids',
        'f1',
      ),
    )
  })

  it('logs a dismiss and greys the card with an Undo', async () => {
    render(<JdStudio />, { wrapper })

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss flag' }))

    await waitFor(() =>
      expect(recordInteraction).toHaveBeenCalledWith(
        'f1',
        expect.objectContaining({ kind: 'dismiss' }),
      ),
    )
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument()
  })
})
