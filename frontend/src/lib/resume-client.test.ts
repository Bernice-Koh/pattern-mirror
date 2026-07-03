import { describe, it, expect, afterEach, vi } from 'vitest'
import { ResumeError, downloadResume, fetchResumeBlob } from './resume-client'

function mockFetch(response: Response) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(response)
}

// A string body, not a Blob: jsdom's Blob lacks `.stream()`, which the Response
// constructor calls, so wrapping a Blob throws in CI. `response.blob()` still works.
function pdfResponse(headers: Record<string, string> = {}): Response {
  return new Response('%PDF-bytes', { status: 200, headers })
}

describe('resume-client', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchResumeBlob GETs the subject resume path', async () => {
    const fetchSpy = mockFetch(pdfResponse())

    await fetchResumeBlob('subj-1', 'fallback.pdf')

    expect(fetchSpy).toHaveBeenCalledWith(
      '/subjects/subj-1/resume',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('uses the server filename from Content-Disposition when present', async () => {
    mockFetch(
      pdfResponse({
        'Content-Disposition': 'attachment; filename="ada-resume.pdf"',
      }),
    )

    const result = await fetchResumeBlob('subj-1', 'fallback.pdf')

    expect(result.filename).toBe('ada-resume.pdf')
  })

  it('falls back to the given name when no Content-Disposition is sent', async () => {
    mockFetch(pdfResponse())

    const result = await fetchResumeBlob('subj-1', 'fallback.pdf')

    expect(result.filename).toBe('fallback.pdf')
  })

  it('throws ResumeError carrying the status on a non-OK response', async () => {
    mockFetch(new Response(null, { status: 404 }))

    await expect(fetchResumeBlob('missing', 'f.pdf')).rejects.toBeInstanceOf(
      ResumeError,
    )
    await expect(fetchResumeBlob('missing', 'f.pdf')).rejects.toMatchObject({
      status: 404,
    })
  })

  it('downloadResume clicks an anchor with the resolved filename and revokes the URL', async () => {
    mockFetch(
      pdfResponse({
        'Content-Disposition': 'attachment; filename="ada-resume.pdf"',
      }),
    )
    const createObjectURL = vi.fn().mockReturnValue('blob:url')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => {})

    await downloadResume('subj-1', 'fallback.pdf')

    expect(clickSpy).toHaveBeenCalledOnce()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:url')
    vi.unstubAllGlobals()
  })
})
