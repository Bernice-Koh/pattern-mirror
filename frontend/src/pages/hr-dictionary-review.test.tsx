import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { HrDictionaryReview } from './hr-dictionary-review'
import { getPendingAdditions, getProposalAudit } from '@/lib/growth-client'
import type { PendingAddition, ProposalAudit } from '@/lib/growth-contract'

const useSearchMock = vi.hoisted(() =>
  vi.fn(() => ({}) as { addition?: string }),
)

vi.mock('@/lib/growth-client', () => ({
  getPendingAdditions: vi.fn(),
  getProposalAudit: vi.fn(),
  decideAddition: vi.fn(),
  GrowthError: class GrowthError extends Error {
    status = 0
  },
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="#">{children}</a>,
  useSearch: useSearchMock,
}))

const getPendingAdditionsMock = vi.mocked(getPendingAdditions)
const getProposalAuditMock = vi.mocked(getProposalAudit)

function addition(index: number): PendingAddition {
  return {
    id: `a${index}`,
    proposal_id: `p${index}`,
    phrase: `phrase ${index}`,
    proposed_category: 'age',
    explanation: 'Youth-coded.',
    status: 'pending',
    created_at: '2026-06-01T00:00:00Z',
    decided_at: null,
    citation: null,
  }
}

const AUDIT: ProposalAudit = {
  proposal_id: 'p1',
  phrase: 'phrase 1',
  lemma_key: 'phrase 1',
  proposed_at: '2026-06-01T00:00:00Z',
  advanced: true,
  arguments: [],
  citation: null,
  decision: null,
  live_entry: null,
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('HrDictionaryReview', () => {
  beforeEach(() => {
    getPendingAdditionsMock.mockReset()
    getProposalAuditMock.mockReset()
    useSearchMock.mockReturnValue({})
  })

  it('lists the pending phrases', async () => {
    getPendingAdditionsMock.mockResolvedValue([addition(1), addition(2)])

    render(<HrDictionaryReview />, { wrapper })

    expect(await screen.findByText('phrase 1')).toBeInTheDocument()
    expect(screen.getByText('phrase 2')).toBeInTheDocument()
  })

  it('shows an empty state when the queue is clear', async () => {
    getPendingAdditionsMock.mockResolvedValue([])

    render(<HrDictionaryReview />, { wrapper })

    expect(
      await screen.findByText('The review queue is clear.'),
    ).toBeInTheDocument()
  })

  it('paginates a queue larger than one page', async () => {
    getPendingAdditionsMock.mockResolvedValue(
      Array.from({ length: 12 }, (_, i) => addition(i + 1)),
    )

    render(<HrDictionaryReview />, { wrapper })

    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('phrase 10')).toBeInTheDocument()
    expect(screen.queryByText('phrase 11')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    expect(screen.getByText('phrase 11')).toBeInTheDocument()
  })

  it('opens the review modal for a phrase', async () => {
    getPendingAdditionsMock.mockResolvedValue([addition(1)])
    getProposalAuditMock.mockResolvedValue(AUDIT)

    render(<HrDictionaryReview />, { wrapper })

    fireEvent.click(await screen.findByText('Review →'))

    expect(
      await screen.findByText('What the review agents said'),
    ).toBeInTheDocument()
    expect(getProposalAuditMock).toHaveBeenCalledWith('p1')
  })

  it('opens the modal for the addition named in the search param', async () => {
    useSearchMock.mockReturnValue({ addition: 'a1' })
    getPendingAdditionsMock.mockResolvedValue([addition(1)])
    getProposalAuditMock.mockResolvedValue(AUDIT)

    render(<HrDictionaryReview />, { wrapper })

    expect(
      await screen.findByText('What the review agents said'),
    ).toBeInTheDocument()
  })
})
