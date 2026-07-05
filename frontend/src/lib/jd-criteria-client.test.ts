import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  confirmJdCriteria,
  draftJdCriteria,
  getJdCriteria,
  JdCriteriaError,
} from './jd-criteria-client'

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('jd-criteria-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the confirmed criteria', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify({ criteria: ['Python', 'Leadership'] }), {
        status: 200,
      }),
    )

    const result = await getJdCriteria('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/jd-criteria',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result.criteria).toEqual(['Python', 'Leadership'])
  })

  it('POSTs the current content to draft criteria', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify({ criteria: ['Drafted'] }), { status: 200 }),
    )

    const result = await draftJdCriteria('doc-1', { content: 'JD text' })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/jd-criteria/draft',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ content: 'JD text' }),
      }),
    )
    expect(result.criteria).toEqual(['Drafted'])
  })

  it('PUTs the confirmed criteria', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify({ criteria: ['Kept'] }), { status: 200 }),
    )

    await confirmJdCriteria('doc-1', { criteria: ['Kept'] })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/jd-criteria',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ criteria: ['Kept'] }),
      }),
    )
  })

  it('throws a JdCriteriaError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 503 }))

    await expect(
      draftJdCriteria('doc-1', { content: 'x' }),
    ).rejects.toMatchObject({
      name: 'JdCriteriaError',
      status: 503,
    })
    expect(new JdCriteriaError(503).status).toBe(503)
  })
})
