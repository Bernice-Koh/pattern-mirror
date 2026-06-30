import { describe, it, expect } from 'vitest'
import { decisionStatement } from '@/lib/decision-statement'
import type { DecisionPattern } from '@/lib/patterns-contract'

function decisionPattern(over: Partial<DecisionPattern> = {}): DecisionPattern {
  return {
    category: 'gender',
    adopted_count: 2,
    rejected_count: 7,
    total_count: 9,
    adoption_rate: 2 / 9,
    p_value: 0.01,
    document_ids: ['d1', 'd2', 'd3'],
    ...over,
  }
}

describe('decisionStatement', () => {
  it('states the adoption split as a flat factual sentence', () => {
    const { sentence } = decisionStatement(decisionPattern())

    expect(sentence).toBe(
      'You revised flagged gender language in 2 of 9 flagged cases.',
    )
  })

  it('anchors the bar on the adoption rate', () => {
    const { rate, rateLabel } = decisionStatement(decisionPattern())

    expect(rate).toBeCloseTo(2 / 9)
    expect(rateLabel).toBe('2 of 9 revised')
  })

  it('formats the eyebrow as category · your decisions', () => {
    const { eyebrow } = decisionStatement(
      decisionPattern({ category: 'family_status' }),
    )

    expect(eyebrow).toBe('Family status · your decisions')
  })

  it('formats the p-value to one significant figure', () => {
    expect(
      decisionStatement(decisionPattern({ p_value: 0.034 })).pValueLabel,
    ).toBe('0.03')
  })

  it('floors a vanishingly small p-value', () => {
    expect(
      decisionStatement(decisionPattern({ p_value: 0.00002 })).pValueLabel,
    ).toBe('< 0.0001')
  })

  it('counts source documents for the citation', () => {
    expect(decisionStatement(decisionPattern()).notesCount).toBe(3)
  })
})
