import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { BehaviouralPatternCard } from './behavioural-pattern-card'
import type { DecisionPattern } from '@/lib/patterns-contract'

vi.mock('@/lib/documents-client', () => ({
  listDocuments: vi.fn().mockResolvedValue([
    {
      id: 'd1',
      doc_type: 'feedback',
      title: 'Backend candidate review',
      role_title: 'Senior Engineer',
      status: 'submitted',
      created_at: '2026-05-01T00:00:00Z',
      updated_at: '2026-05-01T00:00:00Z',
      submitted_at: '2026-05-01T00:00:00Z',
    },
  ]),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}))

const PATTERN: DecisionPattern = {
  category: 'gender',
  adopted_count: 2,
  rejected_count: 7,
  total_count: 9,
  adoption_rate: 2 / 9,
  p_value: 0.01,
  document_ids: ['d1'],
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('BehaviouralPatternCard', () => {
  it('renders the statement, p-value, and citation count', () => {
    render(<BehaviouralPatternCard pattern={PATTERN} />, { wrapper })

    expect(
      screen.getByText(
        'You revised flagged gender language in 2 of 9 flagged cases.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('p = 0.01')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'View 1 notes →' }),
    ).toBeInTheDocument()
  })

  it('drills into the source documents on click', async () => {
    render(<BehaviouralPatternCard pattern={PATTERN} />, { wrapper })

    fireEvent.click(screen.getByRole('button', { name: 'View 1 notes →' }))

    expect(
      await screen.findByText('Backend candidate review'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Hide notes' }),
    ).toBeInTheDocument()
  })
})
