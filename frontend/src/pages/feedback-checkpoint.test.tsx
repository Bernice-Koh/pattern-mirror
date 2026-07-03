import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { getFeedbackContext } from '@/lib/feedback-context-client'
import { listDriftFindings } from '@/lib/drift-client'
import { FeedbackCheckpoint } from './feedback-checkpoint'

vi.mock('@tanstack/react-router', () => ({
  useSearch: () => ({ doc: 'doc-1' }),
}))

// A submitted-context session with a stable document id, so the criteria and drift reads run.
vi.mock('@/components/surface/use-document-session', () => ({
  useDocumentSession: () => ({
    isLoading: false,
    isReadOnly: false,
    documentId: 'doc-1',
    initialContent: '',
    title: '',
    setTitle: vi.fn(),
    content: '',
    setContent: vi.fn(),
    saveState: 'idle',
    submitState: 'idle',
    submit: vi.fn(),
  }),
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
  recommendations: { rationale: 'r', alternatives: ['team contribution'] },
}))

// Stub the editor: surface FLAG to the panel and expose a control that fires a run completion.
vi.mock('@/components/surface/surface-editor', async () => {
  const React = await import('react')
  return {
    SurfaceEditor: React.forwardRef(function MockEditor(
      props: {
        onFlagsChange?: (flags: unknown[]) => void
        onRunComplete?: (runId: string) => void
      },
      ref,
    ) {
      React.useImperativeHandle(ref, () => ({ applyRecommendation: vi.fn() }))
      const { onFlagsChange, onRunComplete } = props
      React.useEffect(() => onFlagsChange?.([FLAG]), [onFlagsChange])
      return React.createElement(
        'button',
        { onClick: () => onRunComplete?.('run-1') },
        'complete-run',
      )
    }),
  }
})

vi.mock('@/lib/feedback-context-client', () => ({
  getFeedbackContext: vi.fn(),
}))
vi.mock('@/lib/drift-client', () => ({ listDriftFindings: vi.fn() }))
vi.mock('@/lib/interaction-client', () => ({
  recordInteraction: vi.fn().mockResolvedValue({}),
}))

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('FeedbackCheckpoint', () => {
  beforeEach(() => {
    vi.mocked(getFeedbackContext).mockResolvedValue({
      role_title: 'Markets Analyst',
      subject_name: 'Taylor Quek',
      criteria: ['Strong SQL', '5+ years Python'],
    })
    vi.mocked(listDriftFindings).mockResolvedValue([
      {
        id: 'd1',
        reference_kind: 'jd_criteria',
        criterion: 'Strong SQL',
        addressed: true,
        evidence: null,
        evidence_start: null,
        evidence_end: null,
      },
      {
        id: 'd2',
        reference_kind: 'jd_criteria',
        criterion: '5+ years Python',
        addressed: false,
        evidence: null,
        evidence_start: null,
        evidence_end: null,
      },
    ])
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders the criteria bar, context chips, and coverage summary', async () => {
    render(<FeedbackCheckpoint />, { wrapper })

    await waitFor(() =>
      expect(screen.getByText('Taylor Quek')).toBeInTheDocument(),
    )
    expect(screen.getByText('Markets Analyst')).toBeInTheDocument()
    // "Strong SQL" appears both as a criteria chip and a coverage row.
    expect(screen.getAllByText('Strong SQL').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('1 of 2 not addressed')).toBeInTheDocument()
  })

  it('lists the bias flags as observations', async () => {
    render(<FeedbackCheckpoint />, { wrapper })

    await waitFor(() =>
      expect(screen.getByText('young rockstar')).toBeInTheDocument(),
    )
    expect(screen.getByText('1 found')).toBeInTheDocument()
    expect(screen.getByText('Race')).toBeInTheDocument()
  })

  it('refetches drift findings when a run completes', async () => {
    render(<FeedbackCheckpoint />, { wrapper })

    await waitFor(() => expect(listDriftFindings).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByText('complete-run'))

    await waitFor(() => expect(listDriftFindings).toHaveBeenCalledTimes(2))
  })
})
