import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DictionaryHealthPanel } from './dictionary-health-panel'
import type { DictionaryHealthReport } from '@/lib/hr-contract'

const ALL_NULL: DictionaryHealthReport = {
  proposal_volume: null,
  agent_agreement_rate: null,
  citation_coverage: null,
  approval_throughput: null,
}

const POPULATED: DictionaryHealthReport = {
  proposal_volume: 11,
  agent_agreement_rate: 0.85,
  citation_coverage: 0.82,
  approval_throughput: 7,
}

describe('DictionaryHealthPanel', () => {
  it('shows an empty state until Dictionary Growth provides data', () => {
    render(<DictionaryHealthPanel report={ALL_NULL} />)

    expect(
      screen.getByText(
        'Dictionary health appears once the dictionary starts growing',
      ),
    ).toBeInTheDocument()
  })

  it('renders the four health stats when data is present', () => {
    render(<DictionaryHealthPanel report={POPULATED} />)

    expect(screen.getByText('11')).toBeInTheDocument()
    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })
})
