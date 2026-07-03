import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  DriftError,
  listDriftFindings,
  recordDriftInteraction,
} from './drift-client'
import type { DriftFinding } from './drift-contract'

const FINDING: DriftFinding = {
  id: 'find-1',
  reference_kind: 'jd_criteria',
  criterion: 'Strong SQL',
  addressed: true,
  evidence: 'handled the SQL question well',
  evidence_start: 0,
  evidence_end: 10,
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('drift-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('listDriftFindings GETs the document findings', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify([FINDING]), { status: 200 }),
    )

    const result = await listDriftFindings('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/drift-findings',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual([FINDING])
  })

  it('recordDriftInteraction POSTs the kind to the finding path', async () => {
    const fetchSpy = mockFetch(
      new Response(
        JSON.stringify({
          id: 'i',
          finding_id: 'find-1',
          kind: 'dismiss',
          dismissed: true,
        }),
        { status: 200 },
      ),
    )

    await recordDriftInteraction('find-1', 'dismiss')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/drift-findings/find-1/interactions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ kind: 'dismiss' }),
      }),
    )
  })

  it('throws DriftError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(listDriftFindings('missing')).rejects.toBeInstanceOf(DriftError)
    await expect(listDriftFindings('missing')).rejects.toMatchObject({
      status: 404,
    })
  })
})
