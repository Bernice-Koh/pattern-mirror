import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { PatternCard } from './pattern-card'
import type { WritingPattern } from '@/lib/patterns-contract'

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

const PATTERN: WritingPattern = {
  mode: 'across_time',
  term: 'sharp',
  category: 'gender',
  dimension: 'gender',
  group_counts: { male: 5, female: 1 },
  supporting_count: 6,
  p_value: 0.0008,
  role_title: null,
  document_ids: ['d1'],
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('PatternCard', () => {
  it('renders the statement, p-value, and citation count', () => {
    render(<PatternCard pattern={PATTERN} />, { wrapper })

    expect(
      screen.getByText(
        '"sharp" appears in 6 documents — 5 about men, 1 about women.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('p = 0.0008')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'View 1 notes →' }),
    ).toBeInTheDocument()
  })

  it('drills into the source documents on click', async () => {
    render(<PatternCard pattern={PATTERN} />, { wrapper })

    fireEvent.click(screen.getByRole('button', { name: 'View 1 notes →' }))

    expect(
      await screen.findByText('Backend candidate review'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Hide notes' }),
    ).toBeInTheDocument()
  })
})
