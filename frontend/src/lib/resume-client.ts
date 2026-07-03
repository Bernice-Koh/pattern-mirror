/** Client for the resume download (#118): GET /subjects/{id}/resume behind the bearer token.
 *  A plain <a download> link can't carry the Authorization header, so the file is fetched through
 *  `apiFetch` and handed to the browser as an object URL. Reused by Feedback and Promotion. */

import { apiFetch } from '@/lib/http'

/** A non-OK response from a resume call, carrying the status so callers can tell a missing resume
 *  (404) apart from a real failure. */
export class ResumeError extends Error {
  readonly status: number

  constructor(status: number) {
    super(`Resume request failed with status ${status}`)
    this.name = 'ResumeError'
    this.status = status
  }
}

export interface ResumeBlob {
  blob: Blob
  filename: string
}

/** Parse the download filename from a Content-Disposition header, if present. */
function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null
  const match = /filename="?([^"]+)"?/.exec(header)
  return match ? match[1] : null
}

/** Fetch a subject's resume file and the filename the server labelled it with. */
export async function fetchResumeBlob(
  subjectId: string,
  fallbackName: string,
): Promise<ResumeBlob> {
  const response = await apiFetch(`/subjects/${subjectId}/resume`, {
    method: 'GET',
  })
  if (!response.ok) throw new ResumeError(response.status)
  const filename =
    filenameFromDisposition(response.headers.get('Content-Disposition')) ??
    fallbackName
  return { blob: await response.blob(), filename }
}

/** Fetch a subject's resume and hand it to the browser as a file download. */
export async function downloadResume(
  subjectId: string,
  fallbackName: string,
): Promise<void> {
  const { blob, filename } = await fetchResumeBlob(subjectId, fallbackName)
  const url = URL.createObjectURL(blob)
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}
