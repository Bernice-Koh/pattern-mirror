import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { DocumentSummary } from '@/lib/documents-contract'
import { DocumentRow } from './document-row'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}))

function summary(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    id: 'd1',
    doc_type: 'jd',
    title: 'Senior Engineer',
    role_title: 'Engineering',
    status: 'submitted',
    created_at: '2026-05-19T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
    submitted_at: '2026-06-02T00:00:00Z',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('DocumentRow', () => {
  it('labels a published JD with its submitted date and role', () => {
    render(<DocumentRow document={summary()} />)
    expect(
      screen.getByText('Published 2 Jun · Engineering'),
    ).toBeInTheDocument()
  })

  it('labels a submitted checkpoint as Submitted, not Published', () => {
    render(
      <DocumentRow
        document={summary({ doc_type: 'feedback', title: 'Note' })}
      />,
    )
    expect(
      screen.getByText('Submitted 2 Jun · Engineering'),
    ).toBeInTheDocument()
  })

  it('omits the role when there is none', () => {
    render(<DocumentRow document={summary({ role_title: null })} />)
    expect(screen.getByText('Published 2 Jun')).toBeInTheDocument()
  })

  it('falls back to the created date when a submission lacks its own timestamp', () => {
    render(
      <DocumentRow
        document={summary({ submitted_at: null, role_title: null })}
      />,
    )
    expect(screen.getByText('Published 19 May')).toBeInTheDocument()
  })

  it('shows a draft without a date', () => {
    render(
      <DocumentRow
        document={summary({ status: 'draft', role_title: 'Associate' })}
      />,
    )
    expect(screen.getByText('Draft · Associate')).toBeInTheDocument()
  })

  it('shows a bare Draft when a draft has no role', () => {
    render(
      <DocumentRow document={summary({ status: 'draft', role_title: null })} />,
    )
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })

  it('uses a type-specific fallback title when untitled', () => {
    render(
      <DocumentRow
        document={summary({ doc_type: 'promotion', title: null })}
      />,
    )
    expect(screen.getByText('Untitled promotion writeup')).toBeInTheDocument()
  })

  it('opens the document in its surface on click', () => {
    render(<DocumentRow document={summary({ doc_type: 'promotion' })} />)

    fireEvent.click(screen.getByRole('button'))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/promotion-writeup',
      search: { doc: 'd1' },
    })
  })
})
