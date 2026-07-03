import { describe, it, expect, afterEach, vi } from 'vitest'
import { getFeedbackContext } from './feedback-context-client'
import type { FeedbackContext } from './feedback-context-contract'

const CONTEXT: FeedbackContext = {
  role_title: 'Markets Analyst',
  subject_name: 'Taylor Quek',
  criteria: ['Strong SQL', '5+ years Python'],
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('feedback-context-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the feedback-context path and returns the context', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(CONTEXT), { status: 200 }),
    )

    const result = await getFeedbackContext('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/feedback-context',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(CONTEXT)
  })

  it('throws on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(getFeedbackContext('missing')).rejects.toThrow(/status 404/)
  })
})
