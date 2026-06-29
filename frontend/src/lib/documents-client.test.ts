import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  createDocument,
  DocumentError,
  getDocument,
  submitDocument,
  updateDraft,
} from './documents-client'
import type { DocumentResponse } from './documents-contract'

const DOCUMENT: DocumentResponse = {
  id: 'doc-1',
  doc_type: 'jd',
  title: 'Senior Engineer',
  status: 'draft',
  content: 'We want a digital native.',
}

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

function okResponse() {
  return new Response(JSON.stringify(DOCUMENT), { status: 200 })
}

describe('documents-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('createDocument POSTs the body as JSON to /documents', async () => {
    const fetchSpy = mockFetch(okResponse())

    const result = await createDocument({ doc_type: 'jd' })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_type: 'jd' }),
      }),
    )
    expect(result).toEqual(DOCUMENT)
  })

  it('getDocument GETs the document by id', async () => {
    const fetchSpy = mockFetch(okResponse())

    const result = await getDocument('doc-1')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(result).toEqual(DOCUMENT)
  })

  it('updateDraft PATCHes the title and content', async () => {
    const fetchSpy = mockFetch(okResponse())

    await updateDraft('doc-1', { title: 'Senior Engineer', content: 'text' })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ title: 'Senior Engineer', content: 'text' }),
      }),
    )
  })

  it('submitDocument POSTs the final content to the submit path', async () => {
    const fetchSpy = mockFetch(okResponse())

    await submitDocument('doc-1', { content: 'final text' })

    expect(fetchSpy).toHaveBeenCalledWith(
      '/documents/doc-1/submit',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ content: 'final text' }),
      }),
    )
  })

  it('throws DocumentError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(getDocument('missing')).rejects.toMatchObject({
      name: 'DocumentError',
      status: 404,
    })
    await expect(getDocument('missing')).rejects.toBeInstanceOf(DocumentError)
  })
})
