import { describe, it, expect, afterEach, vi } from 'vitest'
import { getDictionaryHealth, getEffectiveness, HrError } from './hr-client'
import type { DictionaryHealthReport, EffectivenessReport } from './hr-contract'

const EFFECTIVENESS: EffectivenessReport = {
  adoption_over_time: [
    {
      period: '2026-01',
      adopted_count: 6,
      total_count: 10,
      adoption_rate: 0.6,
    },
  ],
  adoption_by_category: [
    {
      category: 'gender',
      adopted_count: 4,
      total_count: 5,
      adoption_rate: 0.8,
    },
  ],
  adoption_by_doc_type: [
    { doc_type: 'jd', adopted_count: 3, total_count: 4, adoption_rate: 0.75 },
  ],
}

const DICTIONARY_HEALTH: DictionaryHealthReport = {
  proposal_volume: null,
  agent_agreement_rate: null,
  citation_coverage: null,
  approval_throughput: null,
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('hr-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs /hr/effectiveness and returns the report', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(EFFECTIVENESS), { status: 200 }),
    )

    const result = await getEffectiveness()

    expect(fetchSpy).toHaveBeenCalledWith(
      '/hr/effectiveness',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(EFFECTIVENESS)
  })

  it('GETs /hr/dictionary-health and returns the report', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(DICTIONARY_HEALTH), { status: 200 }),
    )

    const result = await getDictionaryHealth()

    expect(fetchSpy).toHaveBeenCalledWith(
      '/hr/dictionary-health',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(DICTIONARY_HEALTH)
  })

  it('throws HrError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 403 }))

    await expect(getEffectiveness()).rejects.toMatchObject({
      name: 'HrError',
      status: 403,
    })
    await expect(getEffectiveness()).rejects.toBeInstanceOf(HrError)
  })
})
