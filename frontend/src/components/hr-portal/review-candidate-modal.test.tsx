import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ReviewCandidateModal } from './review-candidate-modal'
import { decideAddition, getProposalAudit } from '@/lib/growth-client'
import type { PendingAddition, ProposalAudit } from '@/lib/growth-contract'

vi.mock('@/lib/growth-client', () => ({
  getProposalAudit: vi.fn(),
  decideAddition: vi.fn(),
  GrowthError: class GrowthError extends Error {
    status = 0
  },
}))

const getProposalAuditMock = vi.mocked(getProposalAudit)
const decideAdditionMock = vi.mocked(decideAddition)

const ADDITION: PendingAddition = {
  id: 'a1',
  proposal_id: 'p1',
  phrase: 'rockstar',
  proposed_category: 'age',
  explanation: 'Youth-coded phrasing.',
  status: 'pending',
  created_at: '2026-06-01T00:00:00Z',
  decided_at: null,
  citation: null,
}

const AUDIT: ProposalAudit = {
  proposal_id: 'p1',
  phrase: 'rockstar',
  lemma_key: 'rockstar',
  proposed_at: '2026-06-01T00:00:00Z',
  advanced: true,
  arguments: [
    {
      agent_name: 'proposer',
      model: 'm',
      output: { reasoning: 'Skews youthful; deters older applicants.' },
    },
    {
      agent_name: 'skeptic',
      model: 'm',
      output: { reasoning: 'Considered; still merits an entry.' },
    },
    {
      agent_name: 'categorizer',
      model: 'm',
      output: { reasoning: 'General.' },
    },
    {
      agent_name: 'citation',
      model: 'm',
      output: { reasoning: 'Regulatory support exists.' },
    },
  ],
  citation: {
    source_type: 'regulatory',
    title: 'Fair hiring guideline',
    reference: 'TAFEP-2021-3',
    publication_year: 2021,
    finding: 'The phrasing discourages older applicants.',
  },
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

describe('ReviewCandidateModal', () => {
  beforeEach(() => {
    getProposalAuditMock.mockReset()
    decideAdditionMock.mockReset()
  })

  it("shows the four agents' reasoning and the citation found", async () => {
    getProposalAuditMock.mockResolvedValue(AUDIT)

    render(<ReviewCandidateModal addition={ADDITION} onClose={() => {}} />, {
      wrapper,
    })

    expect(
      await screen.findByText('Skews youthful; deters older applicants.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Considered; still merits an entry.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Fair hiring guideline/)).toBeInTheDocument()
    expect(screen.getByText('TAFEP-2021-3')).toBeInTheDocument()
  })

  it('approves through the addition-scoped decision and closes', async () => {
    getProposalAuditMock.mockResolvedValue(AUDIT)
    decideAdditionMock.mockResolvedValue(undefined)
    const onClose = vi.fn()

    render(<ReviewCandidateModal addition={ADDITION} onClose={onClose} />, {
      wrapper,
    })

    fireEvent.click(screen.getByRole('button', { name: 'Approve' }))

    await waitFor(() =>
      expect(decideAdditionMock).toHaveBeenCalledWith('a1', 'approve'),
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('defers without creating a row', async () => {
    getProposalAuditMock.mockResolvedValue(AUDIT)
    decideAdditionMock.mockResolvedValue(undefined)

    render(<ReviewCandidateModal addition={ADDITION} onClose={() => {}} />, {
      wrapper,
    })

    fireEvent.click(screen.getByRole('button', { name: 'Defer' }))

    await waitFor(() =>
      expect(decideAdditionMock).toHaveBeenCalledWith('a1', 'defer'),
    )
  })
})
