import { describe, it, expect, afterEach, vi } from 'vitest'
import { getPromotionContext } from './promotion-context-client'
import type { PromotionContext } from './promotion-context-contract'

const CONTEXT: PromotionContext = {
  role_title: 'Director — Delivery Engineering',
  subject_id: 'subj-1',
  subject_name: 'Nadia Farouk',
  criteria: ['Owns delivery', 'Cross-team impact'],
  corroboration: [
    {
      criterion: 'Owns delivery',
      corroborated: true,
      evidence: 'owns the pipeline',
    },
    { criterion: 'Cross-team impact', corroborated: false, evidence: null },
  ],
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('promotion-context-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the promotion-context path and returns the context', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(CONTEXT), { status: 200 }),
    )

    const result = await getPromotionContext('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/promotion-context',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(CONTEXT)
  })

  it('throws on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(getPromotionContext('missing')).rejects.toThrow(/status 404/)
  })
})
