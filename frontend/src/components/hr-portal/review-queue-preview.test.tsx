import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ReviewQueuePreview } from './review-queue-preview'
import { getPendingAdditions } from '@/lib/growth-client'
import type { PendingAddition } from '@/lib/growth-contract'

vi.mock('@/lib/growth-client', () => ({ getPendingAdditions: vi.fn() }))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="#">{children}</a>,
  useNavigate: () => vi.fn(),
}))

const getPendingAdditionsMock = vi.mocked(getPendingAdditions)

function addition(overrides: Partial<PendingAddition> = {}): PendingAddition {
  return {
    id: 'a1',
    proposal_id: 'p1',
    phrase: 'rockstar',
    proposed_category: 'age',
    explanation: 'Youth-coded.',
    status: 'pending',
    created_at: '2026-06-01T00:00:00Z',
    decided_at: null,
    citation: null,
    ...overrides,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('ReviewQueuePreview', () => {
  beforeEach(() => {
    getPendingAdditionsMock.mockReset()
  })

  it('previews the pending phrases with a link to the full queue', async () => {
    getPendingAdditionsMock.mockResolvedValue([
      addition({ id: 'a1', phrase: 'rockstar' }),
      addition({ id: 'a2', proposal_id: 'p2', phrase: 'cultural fit' }),
    ])

    render(<ReviewQueuePreview />, { wrapper })

    expect(await screen.findByText('rockstar')).toBeInTheDocument()
    expect(screen.getByText('cultural fit')).toBeInTheDocument()
    expect(screen.getByText('Review all (2) →')).toBeInTheDocument()
  })

  it('shows a clear-queue empty state when nothing is pending', async () => {
    getPendingAdditionsMock.mockResolvedValue([])

    render(<ReviewQueuePreview />, { wrapper })

    expect(
      await screen.findByText('The review queue is clear'),
    ).toBeInTheDocument()
  })
})
