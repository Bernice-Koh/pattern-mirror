import { describe, it, expect, afterEach, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { listDriftFindings } from '@/lib/drift-client'
import type { DriftFinding } from '@/lib/drift-contract'
import { useDriftFindings } from './use-drift-findings'

vi.mock('@/lib/drift-client', () => ({ listDriftFindings: vi.fn() }))

const FINDING: DriftFinding = {
  id: 'f1',
  reference_kind: 'jd_criteria',
  criterion: 'Strong SQL',
  addressed: true,
  evidence: null,
  evidence_start: null,
  evidence_end: null,
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useDriftFindings', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('reads the document findings and refetches on demand', async () => {
    vi.mocked(listDriftFindings).mockResolvedValue([FINDING])

    const { result } = renderHook(() => useDriftFindings('doc-1'), { wrapper })

    await waitFor(() => expect(result.current.findings).toEqual([FINDING]))
    expect(listDriftFindings).toHaveBeenCalledTimes(1)

    await act(async () => result.current.refetch())

    await waitFor(() => expect(listDriftFindings).toHaveBeenCalledTimes(2))
  })

  it('is disabled without a document', () => {
    renderHook(() => useDriftFindings(null), { wrapper })

    expect(listDriftFindings).not.toHaveBeenCalled()
  })
})
