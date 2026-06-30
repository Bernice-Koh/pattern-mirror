import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { HrPortal } from './hr-portal'
import { getDictionaryHealth, getEffectiveness } from '@/lib/hr-client'

vi.mock('@/lib/hr-client', () => ({
  getEffectiveness: vi.fn(),
  getDictionaryHealth: vi.fn(),
}))

const getEffectivenessMock = vi.mocked(getEffectiveness)
const getDictionaryHealthMock = vi.mocked(getDictionaryHealth)

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

const ALL_NULL_HEALTH = {
  proposal_volume: null,
  agent_agreement_rate: null,
  citation_coverage: null,
  approval_throughput: null,
}

describe('HrPortal', () => {
  beforeEach(() => {
    getEffectivenessMock.mockReset()
    getDictionaryHealthMock.mockReset()
  })

  it('renders the headline, effectiveness, and dictionary panels from the aggregates', async () => {
    getEffectivenessMock.mockResolvedValue({
      adoption_over_time: [],
      adoption_by_category: [],
      adoption_by_doc_type: [
        {
          doc_type: 'feedback',
          adopted_count: 0,
          total_count: 10,
          adoption_rate: 0,
        },
      ],
    })
    getDictionaryHealthMock.mockResolvedValue(ALL_NULL_HEALTH)

    render(<HrPortal />, { wrapper })

    expect(screen.getByText('Is it working?')).toBeInTheDocument()
    expect(await screen.findByText('Interview feedback')).toBeInTheDocument()
    expect(screen.getByText('Where bias appears most')).toBeInTheDocument()
    expect(screen.getByText('Words to review')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Dictionary health appears once the dictionary starts growing',
      ),
    ).toBeInTheDocument()
  })

  it('keeps the structural privacy boundary visible to HR', () => {
    getEffectivenessMock.mockResolvedValue({
      adoption_over_time: [],
      adoption_by_category: [],
      adoption_by_doc_type: [],
    })
    getDictionaryHealthMock.mockResolvedValue(ALL_NULL_HEALTH)

    render(<HrPortal />, { wrapper })

    expect(
      screen.getByText(/No individual manager or candidate writing is/),
    ).toBeInTheDocument()
  })
})
