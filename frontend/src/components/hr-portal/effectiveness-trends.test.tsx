import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EffectivenessTrends } from './effectiveness-trends'
import type { EffectivenessReport } from '@/lib/hr-contract'

const FULL: EffectivenessReport = {
  adoption_over_time: [
    {
      period: '2026-01',
      adopted_count: 0,
      total_count: 100,
      adoption_rate: 0,
    },
    { period: '2026-06', adopted_count: 0, total_count: 66, adoption_rate: 0 },
  ],
  adoption_by_category: [
    { category: 'gender', adopted_count: 0, total_count: 60, adoption_rate: 0 },
    { category: 'age', adopted_count: 0, total_count: 40, adoption_rate: 0 },
  ],
  adoption_by_doc_type: [
    {
      doc_type: 'feedback',
      adopted_count: 0,
      total_count: 75,
      adoption_rate: 0,
    },
    { doc_type: 'jd', adopted_count: 0, total_count: 25, adoption_rate: 0 },
  ],
}

const EMPTY: EffectivenessReport = {
  adoption_over_time: [],
  adoption_by_category: [],
  adoption_by_doc_type: [],
}

describe('EffectivenessTrends', () => {
  it('renders the volume trend with a derived drop caption and month labels', () => {
    render(<EffectivenessTrends report={FULL} />)

    expect(screen.getByText('Bias flags raised over time')).toBeInTheDocument()
    expect(screen.getByText('Jan')).toBeInTheDocument()
    expect(screen.getByText('Jun')).toBeInTheDocument()
    expect(
      screen.getByText('Down 34% firm-wide since Jan.'),
    ).toBeInTheDocument()
  })

  it('renders share-of-flags by document type and by characteristic', () => {
    render(<EffectivenessTrends report={FULL} />)

    expect(screen.getByText('Where bias appears most')).toBeInTheDocument()
    expect(screen.getByText('Interview feedback')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()

    expect(screen.getByText('Most-flagged characteristics')).toBeInTheDocument()
    expect(screen.getByText('Gender')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
  })

  it('shows an empty state for each dimension with no data', () => {
    render(<EffectivenessTrends report={EMPTY} />)

    expect(screen.getByText('Not enough history yet')).toBeInTheDocument()
    expect(screen.getByText('No document-type data yet')).toBeInTheDocument()
    expect(screen.getByText('No characteristic data yet')).toBeInTheDocument()
  })
})
