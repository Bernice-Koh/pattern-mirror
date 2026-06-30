import { describe, it, expect } from 'vitest'
import { patternStatement } from '@/lib/pattern-statement'
import type { WritingPattern } from '@/lib/patterns-contract'

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

describe('patternStatement', () => {
  it('states an asymmetric split as a flat factual breakdown', () => {
    const { sentence } = patternStatement(writingPattern())

    expect(sentence).toBe(
      '"sharp" appears in 6 documents — 5 about men, 1 about women.',
    )
  })

  it('collapses an all-one-group split to "all N about …"', () => {
    const { sentence, ratio, ratioLabel } = patternStatement(
      writingPattern({
        group_counts: { male: 5, female: 0 },
        supporting_count: 5,
        document_ids: ['d1', 'd2', 'd3', 'd4', 'd5'],
      }),
    )

    expect(sentence).toBe('"sharp" appears in 5 documents — all 5 about men.')
    expect(ratio).toBe(1)
    expect(ratioLabel).toBe('5 of 5 men')
  })

  it('reports the dominant group ratio for the bar', () => {
    const { ratio, ratioLabel } = patternStatement(writingPattern())

    expect(ratio).toBeCloseTo(5 / 6)
    expect(ratioLabel).toBe('5 of 6 men')
  })

  it('formats the eyebrow as category · word choice', () => {
    const { eyebrow } = patternStatement(
      writingPattern({ category: 'family_status' }),
    )

    expect(eyebrow).toBe('Family status · word choice')
  })

  it('formats a small p-value to one significant figure', () => {
    expect(
      patternStatement(writingPattern({ p_value: 0.0008 })).pValueLabel,
    ).toBe('0.0008')
    expect(
      patternStatement(writingPattern({ p_value: 0.034 })).pValueLabel,
    ).toBe('0.03')
  })

  it('floors a vanishingly small p-value', () => {
    expect(
      patternStatement(writingPattern({ p_value: 0.00002 })).pValueLabel,
    ).toBe('< 0.0001')
  })

  it('counts source documents for the citation', () => {
    expect(patternStatement(writingPattern()).notesCount).toBe(6)
  })

  it('guards against a zero supporting total', () => {
    const { ratio } = patternStatement(
      writingPattern({
        group_counts: { male: 0, female: 0 },
        supporting_count: 0,
      }),
    )

    expect(ratio).toBe(0)
  })

  it('falls back to the raw group key for an unmapped group', () => {
    const { sentence } = patternStatement(
      writingPattern({
        group_counts: { nonbinary: 4, male: 1 },
        supporting_count: 5,
      }),
    )

    expect(sentence).toBe(
      '"sharp" appears in 5 documents — 4 about nonbinary, 1 about men.',
    )
  })
})
