import { describe, it, expect, afterEach, vi } from 'vitest'
import { recordInteraction, InteractionError } from './interaction-client'
import type {
  InteractionRequest,
  InteractionResponse,
} from './interaction-contract'

const REQUEST: InteractionRequest = {
  kind: 'accept',
  accepted_alternative: 'recent graduate',
}

const RESPONSE: InteractionResponse = {
  id: 'interaction-1',
  flag_id: 'flag-1',
  kind: 'accept',
  dismissed: false,
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('recordInteraction', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs the interaction as JSON to the flag-scoped endpoint', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(RESPONSE), { status: 200 }),
    )

    await recordInteraction('flag-1', REQUEST)

    expect(fetchSpy).toHaveBeenCalledWith(
      '/flags/flag-1/interactions',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(REQUEST),
      }),
    )
  })

  it('returns the parsed response body', async () => {
    mockFetch(new Response(JSON.stringify(RESPONSE), { status: 200 }))

    await expect(recordInteraction('flag-1', REQUEST)).resolves.toEqual(
      RESPONSE,
    )
  })

  it('throws InteractionError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(recordInteraction('flag-1', REQUEST)).rejects.toMatchObject({
      name: 'InteractionError',
      status: 404,
    })
    await expect(recordInteraction('flag-1', REQUEST)).rejects.toBeInstanceOf(
      InteractionError,
    )
  })
})
