import { describe, it, expect, afterEach, vi } from 'vitest'
import { getPatterns, PatternError } from './patterns-client'
import type { PatternReport } from './patterns-contract'

const REPORT: PatternReport = {
  writing_patterns: [
    {
      mode: 'across_time',
      term: 'sharp',
      category: 'gender',
      dimension: 'gender',
      group_counts: { male: 5, female: 1 },
      supporting_count: 6,
      p_value: 0.0008,
      role_title: null,
      document_ids: ['d1', 'd2'],
    },
  ],
  decision_patterns: [],
  adoption_trend: [],
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('patterns-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs /patterns and returns the report', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(REPORT), { status: 200 }),
    )

    const result = await getPatterns()

    expect(fetchSpy).toHaveBeenCalledWith(
      '/patterns',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(REPORT)
  })

  it('throws PatternError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 500 }))

    await expect(getPatterns()).rejects.toMatchObject({
      name: 'PatternError',
      status: 500,
    })
    await expect(getPatterns()).rejects.toBeInstanceOf(PatternError)
  })
})
