import { describe, it, expect } from 'vitest'
import { buildRubricCoverage, derivePeerSynthesis } from './promotion-coverage'
import type { DriftFinding } from './drift-contract'
import type { PeerCorroboration } from './promotion-context-contract'

function finding(criterion: string, addressed: boolean): DriftFinding {
  return {
    id: `f-${criterion}`,
    reference_kind: 'promotion_rubric',
    criterion,
    addressed,
    evidence: null,
    evidence_start: null,
    evidence_end: null,
  }
}

const RUBRIC = ['Owns delivery', 'Cross-team impact', 'Mentorship']
const CORROBORATION: PeerCorroboration[] = [
  {
    criterion: 'Owns delivery',
    corroborated: true,
    evidence: 'owns the pipeline',
  },
  {
    criterion: 'Cross-team impact',
    corroborated: true,
    evidence: 'drove the review',
  },
  { criterion: 'Mentorship', corroborated: false, evidence: null },
]

describe('buildRubricCoverage', () => {
  it('shows "not yet checked" before a run, with the static peer signal', () => {
    const items = buildRubricCoverage(RUBRIC, [], CORROBORATION)

    expect(items.map((i) => i.statusLabel)).toEqual([
      'not yet checked',
      'not yet checked',
      'not yet checked',
    ])
    expect(items[0].corroboration).toEqual({
      corroborated: true,
      label: 'peers agree',
    })
    expect(items[2].corroboration).toEqual({
      corroborated: false,
      label: 'peers differ',
    })
  })

  it('reflects the live writeup coverage after a run', () => {
    const findings = [
      finding('Owns delivery', true),
      finding('Cross-team impact', false),
      finding('Mentorship', false),
    ]

    const items = buildRubricCoverage(RUBRIC, findings, CORROBORATION)

    expect(items[0]).toMatchObject({
      addressed: true,
      statusLabel: 'evidenced',
    })
    expect(items[1]).toMatchObject({
      addressed: false,
      statusLabel: 'not evidenced',
    })
  })

  it('matches a finding to its rubric criterion despite case/whitespace', () => {
    const items = buildRubricCoverage(
      ['Owns delivery'],
      [finding('owns   delivery', true)],
      [],
    )

    expect(items[0]).toMatchObject({
      addressed: true,
      statusLabel: 'evidenced',
    })
  })

  it('omits the peer pill for a criterion with no corroboration entry', () => {
    const items = buildRubricCoverage(['Owns delivery'], [], [])

    expect(items[0].corroboration).toBeUndefined()
  })
})

describe('derivePeerSynthesis', () => {
  it('returns null when peers evidence nothing', () => {
    expect(
      derivePeerSynthesis(
        [],
        [{ criterion: 'Owns delivery', corroborated: false, evidence: null }],
      ),
    ).toBeNull()
  })

  it('prompts to run a check before there are findings', () => {
    const result = derivePeerSynthesis([], CORROBORATION)

    expect(result?.lead).toContain('Owns delivery and Cross-team impact')
    expect(result?.synthesis).toMatch(/run a check/i)
  })

  it('names the peer-backed criteria the writeup has not evidenced', () => {
    const findings = [
      finding('Owns delivery', false),
      finding('Cross-team impact', true),
    ]

    const result = derivePeerSynthesis(findings, CORROBORATION)

    expect(result?.synthesis).toContain('Owns delivery')
    expect(result?.synthesis).not.toContain('Cross-team impact')
    expect(result?.synthesis).toMatch(/not yet in yours/)
  })

  it('acknowledges when the writeup already evidences the peer-backed criteria', () => {
    const findings = [
      finding('Owns delivery', true),
      finding('Cross-team impact', true),
    ]

    const result = derivePeerSynthesis(findings, CORROBORATION)

    expect(result?.synthesis).toMatch(/already evidences/i)
  })
})
