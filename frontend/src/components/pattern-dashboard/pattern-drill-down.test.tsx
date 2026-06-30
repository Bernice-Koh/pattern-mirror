import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { PatternDrillDown } from './pattern-drill-down'

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

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('PatternDrillDown', () => {
  it('lists the source documents matching the pattern ids', async () => {
    render(<PatternDrillDown documentIds={['d1']} />, { wrapper })

    expect(
      await screen.findByText('Backend candidate review'),
    ).toBeInTheDocument()
  })

  it('shows an unavailable note when no document matches', async () => {
    render(<PatternDrillDown documentIds={['gone']} />, { wrapper })

    expect(
      await screen.findByText('Source documents are unavailable.'),
    ).toBeInTheDocument()
  })
})
