import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { YourPatterns } from './your-patterns'
import { getPatterns } from '@/lib/patterns-client'
import type {
  DecisionPattern,
  PatternReport,
  WritingPattern,
} from '@/lib/patterns-contract'

vi.mock('@/lib/patterns-client', () => ({
  getPatterns: vi.fn(),
}))

vi.mock('@/lib/documents-client', () => ({
  listDocuments: vi.fn().mockResolvedValue([]),
}))

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => vi.fn(),
}))

const getPatternsMock = vi.mocked(getPatterns)

function report(
  writing: WritingPattern[],
  decision: DecisionPattern[] = [],
): PatternReport {
  return {
    writing_patterns: writing,
    decision_patterns: decision,
    adoption_trend: [],
    flag_volume_trend: [],
    category_improvements: [],
  }
}

function writingPattern(over: Partial<WritingPattern> = {}): WritingPattern {
  return {
    mode: 'across_time',
    term: 'sharp',
    category: 'gender',
    dimension: 'gender',
    group_counts: { male: 5, female: 1 },
    supporting_count: 6,
    p_value: 0.0008,
    role_title: null,
    document_ids: ['d1', 'd2', 'd3', 'd4', 'd5', 'd6'],
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

describe('YourPatterns', () => {
  beforeEach(() => {
    getPatternsMock.mockReset()
  })

  it('renders a card per significant writing pattern, grouped by scope', async () => {
    getPatternsMock.mockResolvedValue(
      report([
        writingPattern(),
        writingPattern({
          mode: 'per_role',
          term: 'polished',
          group_counts: { female: 4, male: 0 },
          supporting_count: 4,
          role_title: 'Product Designer',
          document_ids: ['p1', 'p2', 'p3', 'p4'],
        }),
      ]),
    )

    render(<YourPatterns />, { wrapper })

    expect(
      await screen.findByText(
        '"sharp" appears in 6 documents — 5 about men, 1 about women.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        '"polished" appears in 4 documents — all 4 about women.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Across your history')).toBeInTheDocument()
    expect(screen.getByText('Product Designer')).toBeInTheDocument()
  })

  it('suppresses a per-role card that duplicates an across-history one', async () => {
    getPatternsMock.mockResolvedValue(
      report([
        writingPattern({ term: 'sharp', role_title: null }),
        // Same term + category as the across-history pattern, scoped to a role that dominates the
        // manager's writing — a duplicate, so its role section should not appear at all.
        writingPattern({
          mode: 'per_role',
          term: 'sharp',
          role_title: 'Markets Analyst',
        }),
      ]),
    )

    render(<YourPatterns />, { wrapper })

    expect(await screen.findByText('Across your history')).toBeInTheDocument()
    expect(screen.queryByText('Markets Analyst')).not.toBeInTheDocument()
    // The pattern still appears once, under the whole-history heading.
    expect(
      screen.getAllByText(
        '"sharp" appears in 6 documents — 5 about men, 1 about women.',
      ),
    ).toHaveLength(1)
  })

  it('falls back to a generic scope label for a per-role pattern with no role title', async () => {
    getPatternsMock.mockResolvedValue(
      report([
        writingPattern({
          mode: 'per_role',
          role_title: null,
          term: 'aggressive',
        }),
      ]),
    )

    render(<YourPatterns />, { wrapper })

    expect(await screen.findByText('A role')).toBeInTheDocument()
  })

  it('shows an empty state when nothing clears the threshold', async () => {
    getPatternsMock.mockResolvedValue(report([]))

    render(<YourPatterns />, { wrapper })

    expect(
      await screen.findByText(/No clear patterns have emerged/),
    ).toBeInTheDocument()
  })

  it('renders the behavioural-reflection layer over decision patterns', async () => {
    getPatternsMock.mockResolvedValue(
      report(
        [],
        [
          {
            category: 'gender',
            adopted_count: 2,
            rejected_count: 7,
            total_count: 9,
            adoption_rate: 2 / 9,
            p_value: 0.01,
            document_ids: ['d1'],
          },
        ],
      ),
    )

    render(<YourPatterns />, { wrapper })

    expect(
      await screen.findByText(
        'You revised flagged gender language in 2 of 9 flagged cases.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText("How you've responded to flags"),
    ).toBeInTheDocument()
  })
})
