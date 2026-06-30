import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { BehaviouralReflection } from './behavioural-reflection'
import type {
  AdoptionTrendPoint,
  DecisionPattern,
} from '@/lib/patterns-contract'

vi.mock('@/lib/documents-client', () => ({
  listDocuments: vi.fn().mockResolvedValue([]),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}))

function decisionPattern(over: Partial<DecisionPattern> = {}): DecisionPattern {
  return {
    category: 'gender',
    adopted_count: 2,
    rejected_count: 7,
    total_count: 9,
    adoption_rate: 2 / 9,
    p_value: 0.01,
    document_ids: ['d1', 'd2'],
    ...over,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  )
}

describe('BehaviouralReflection', () => {
  it('renders a card per significant decision pattern', () => {
    render(
      <BehaviouralReflection
        patterns={[
          decisionPattern(),
          decisionPattern({
            category: 'age',
            adopted_count: 8,
            rejected_count: 1,
            total_count: 9,
            adoption_rate: 8 / 9,
          }),
        ]}
        trend={[]}
      />,
      { wrapper },
    )

    expect(
      screen.getByText(
        'You revised flagged gender language in 2 of 9 flagged cases.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'You revised flagged age language in 8 of 9 flagged cases.',
      ),
    ).toBeInTheDocument()
  })

  it('renders the adoption-rate trend with month labels and a first-to-last caption', () => {
    const trend: AdoptionTrendPoint[] = [
      {
        period: '2026-01',
        adopted_count: 2,
        total_count: 9,
        adoption_rate: 0.22,
      },
      {
        period: '2026-06',
        adopted_count: 6,
        total_count: 9,
        adoption_rate: 0.64,
      },
    ]

    render(<BehaviouralReflection patterns={[]} trend={trend} />, { wrapper })

    expect(screen.getByText('Adoption rate over time')).toBeInTheDocument()
    expect(screen.getByText('Jan')).toBeInTheDocument()
    expect(screen.getByText('Jun')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Your adoption rate went from 22% in Jan to 64% in Jun.',
      ),
    ).toBeInTheDocument()
  })

  it('omits the trend panel when there is no trend data', () => {
    render(
      <BehaviouralReflection patterns={[decisionPattern()]} trend={[]} />,
      {
        wrapper,
      },
    )

    expect(
      screen.queryByText('Adoption rate over time'),
    ).not.toBeInTheDocument()
  })

  it('renders the trend chart without a delta caption for a single period', () => {
    render(
      <BehaviouralReflection
        patterns={[]}
        trend={[
          {
            period: '2026-03',
            adopted_count: 1,
            total_count: 2,
            adoption_rate: 0.5,
          },
        ]}
      />,
      { wrapper },
    )

    expect(screen.getByText('Mar')).toBeInTheDocument()
    expect(
      screen.queryByText(/Your adoption rate went from/),
    ).not.toBeInTheDocument()
  })

  it('falls back to the raw period for an unexpected month', () => {
    render(
      <BehaviouralReflection
        patterns={[]}
        trend={[
          {
            period: '2026-13',
            adopted_count: 0,
            total_count: 1,
            adoption_rate: 0,
          },
        ]}
      />,
      { wrapper },
    )

    expect(screen.getByText('2026-13')).toBeInTheDocument()
  })

  it('shows an empty state when no decision pattern clears the threshold', () => {
    render(<BehaviouralReflection patterns={[]} trend={[]} />, { wrapper })

    expect(
      screen.getByText(/No decision patterns have cleared/),
    ).toBeInTheDocument()
  })
})
