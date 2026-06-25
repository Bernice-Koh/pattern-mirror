import { describe, it, expect, afterEach, vi } from 'vitest'
import { analyzeDocument, AnalyzeError } from './analyze-client'
import type { AnalyzeRequest, AnalyzeResponse } from './analyze-contract'

const REQUEST: AnalyzeRequest = {
  doc_type: 'jd',
  content: 'an aggressive leader',
}

const RESPONSE: AnalyzeResponse = {
  document_id: 'doc-1',
  analysis_run_id: 'run-1',
  content_hash: 'hash-1',
  flags: [],
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('analyzeDocument', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs the request as JSON to /analyze', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(RESPONSE), { status: 200 }),
    )

    await analyzeDocument(REQUEST)

    expect(fetchSpy).toHaveBeenCalledWith(
      '/analyze',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(REQUEST),
      }),
    )
  })

  it('returns the parsed response body', async () => {
    mockFetch(new Response(JSON.stringify(RESPONSE), { status: 200 }))

    await expect(analyzeDocument(REQUEST)).resolves.toEqual(RESPONSE)
  })

  it('forwards an abort signal to fetch', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(RESPONSE), { status: 200 }),
    )
    const controller = new AbortController()

    await analyzeDocument(REQUEST, controller.signal)

    expect(fetchSpy).toHaveBeenCalledWith(
      '/analyze',
      expect.objectContaining({ signal: controller.signal }),
    )
  })

  it('throws AnalyzeError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 500 }))

    await expect(analyzeDocument(REQUEST)).rejects.toMatchObject({
      name: 'AnalyzeError',
      status: 500,
    })
    await expect(analyzeDocument(REQUEST)).rejects.toBeInstanceOf(AnalyzeError)
  })
})
