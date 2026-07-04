import { describe, it, expect, afterEach, vi } from 'vitest'
import { listFlags, FlagsError } from './flags-client'
import type { CitedFlag } from './analyze-contract'

const FLAGS: CitedFlag[] = [
  {
    id: 'f1',
    source_stage: 'dictionary',
    category: 'age',
    raw_span: 'digital native',
    start_offset: 10,
    end_offset: 24,
    explanation: "'digital native' is age-coded.",
    citation: {
      source_type: 'tafep',
      title: 'TAFEP',
      reference: 'tafep-2021',
      publication_year: 2021,
      finding: null,
    },
    recommendations: null,
  },
]

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('listFlags', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the document flags path', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(FLAGS), { status: 200 }),
    )

    await listFlags('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/flags',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('returns the parsed flags', async () => {
    mockFetch(new Response(JSON.stringify(FLAGS), { status: 200 }))

    await expect(listFlags('doc-1')).resolves.toEqual(FLAGS)
  })

  it('throws FlagsError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(listFlags('doc-1')).rejects.toMatchObject({
      name: 'FlagsError',
      status: 404,
    })
    await expect(listFlags('doc-1')).rejects.toBeInstanceOf(FlagsError)
  })
})
