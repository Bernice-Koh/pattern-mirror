import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { HrHeadline } from './hr-headline'
import type { EffectivenessReport } from '@/lib/hr-contract'

const FULL: EffectivenessReport = {
  adoption_over_time: [
    {
      period: '2026-01',
      adopted_count: 50,
      total_count: 100,
      adoption_rate: 0.5,
    },
    {
      period: '2026-06',
      adopted_count: 40,
      total_count: 66,
      adoption_rate: 0.61,
    },
  ],
  adoption_by_category: [],
  adoption_by_doc_type: [],
}

const EMPTY: EffectivenessReport = {
  adoption_over_time: [],
  adoption_by_category: [],
  adoption_by_doc_type: [],
}

describe('HrHeadline', () => {
  it('derives the bias-drop and revision-rate cards from the aggregate', () => {
    render(<HrHeadline report={FULL} />)

    expect(screen.getByText('Bias-coded language')).toBeInTheDocument()
    expect(screen.getByText('↓')).toBeInTheDocument()
    expect(screen.getByText('Flagged language revised')).toBeInTheDocument()
    expect(screen.getByText('54%')).toBeInTheDocument()
  })

  it('summarises only the figures that are available', () => {
    render(<HrHeadline report={FULL} />)

    expect(screen.getByText(/down 34%/)).toBeInTheDocument()
    expect(
      screen.getByText(/revise 54% of flagged language/),
    ).toBeInTheDocument()
  })

  it('leaves unavailable cards pending and falls back to a neutral summary', () => {
    render(<HrHeadline report={EMPTY} />)

    expect(screen.getAllByText('—')).toHaveLength(4)
    expect(
      screen.getByText(
        "Firm-level impact will appear here as the firm's history grows.",
      ),
    ).toBeInTheDocument()
  })
})
