import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  decideAddition,
  getPendingAdditions,
  getProposalAudit,
  GrowthError,
} from './growth-client'
import type { PendingAddition, ProposalAudit } from './growth-contract'

const ADDITION: PendingAddition = {
  id: 'a1',
  proposal_id: 'p1',
  phrase: 'rockstar',
  proposed_category: 'age',
  explanation: 'Youth-coded.',
  status: 'pending',
  created_at: '2026-06-01T00:00:00Z',
  decided_at: null,
  citation: null,
}

const AUDIT: ProposalAudit = {
  proposal_id: 'p1',
  phrase: 'rockstar',
  lemma_key: 'rockstar',
  proposed_at: '2026-06-01T00:00:00Z',
  advanced: true,
  arguments: [],
  citation: null,
  decision: null,
  live_entry: null,
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

describe('growth-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('GETs the pending additions', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify([ADDITION]), { status: 200 }),
    )

    const result = await getPendingAdditions()

    expect(fetchSpy).toHaveBeenCalledWith(
      '/growth/pending-additions',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual([ADDITION])
  })

  it('GETs a proposal audit by id', async () => {
    const fetchSpy = mockFetch(
      new Response(JSON.stringify(AUDIT), { status: 200 }),
    )

    const result = await getProposalAudit('p1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/growth/proposals/p1/audit',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(AUDIT)
  })

  it('POSTs an approve decision to the addition-scoped path', async () => {
    const fetchSpy = mockFetch(new Response(null, { status: 200 }))

    await decideAddition('a1', 'approve')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/growth/pending-additions/a1/approve',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('throws GrowthError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 409 }))

    await expect(decideAddition('a1', 'reject')).rejects.toMatchObject({
      name: 'GrowthError',
      status: 409,
    })
    mockFetch(new Response(null, { status: 403 }))
    await expect(getPendingAdditions()).rejects.toBeInstanceOf(GrowthError)
  })
})
