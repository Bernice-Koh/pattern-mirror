import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { listDocuments } from '@/lib/documents-client'
import { MyDocuments } from './my-documents'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}))

vi.mock('@/lib/documents-client', () => ({
  listDocuments: vi.fn(),
}))

const listDocumentsMock = vi.mocked(listDocuments)

const DOCS = [
  {
    id: 'd1',
    doc_type: 'jd' as const,
    title: 'Senior Engineer',
    role_title: 'Engineering',
    status: 'submitted' as const,
    created_at: '2026-06-02T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
    submitted_at: '2026-06-02T00:00:00Z',
  },
  {
    id: 'd2',
    doc_type: 'feedback' as const,
    title: 'Interview feedback',
    role_title: 'Associate',
    status: 'draft' as const,
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
    submitted_at: null,
  },
]

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  listDocumentsMock.mockResolvedValue(DOCS)
})

describe('MyDocuments', () => {
  it('lists the active type and hides the others', async () => {
    render(<MyDocuments />, { wrapper })

    expect(await screen.findByText('Senior Engineer')).toBeInTheDocument()
    expect(
      screen.getByText('Published 2 Jun · Engineering'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Interview feedback')).toBeNull()
  })

  it('switches the listing when another type tab is chosen', async () => {
    render(<MyDocuments />, { wrapper })
    await screen.findByText('Senior Engineer')

    fireEvent.click(screen.getByRole('button', { name: 'Feedback' }))

    expect(await screen.findByText('Interview feedback')).toBeInTheDocument()
    expect(screen.getByText('Draft · Associate')).toBeInTheDocument()
    expect(screen.queryByText('Senior Engineer')).toBeNull()
  })

  it('shows an empty state for a type with no documents', async () => {
    render(<MyDocuments />, { wrapper })
    await screen.findByText('Senior Engineer')

    fireEvent.click(screen.getByRole('button', { name: 'Promotion' }))

    expect(await screen.findByText('Nothing here yet.')).toBeInTheDocument()
  })

  it('opens a document in its surface on click', async () => {
    render(<MyDocuments />, { wrapper })
    const row = await screen.findByText('Senior Engineer')

    fireEvent.click(row)

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/jd-studio',
      search: { doc: 'd1' },
    })
  })
})
