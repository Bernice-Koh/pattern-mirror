import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { downloadResume } from '@/lib/resume-client'

interface ResumeDownloadProps {
  subjectId: string | null | undefined
  subjectName: string | null | undefined
}

const LABELS = {
  idle: 'Download résumé',
  downloading: 'Preparing…',
  error: 'Retry download',
} as const

/** Résumé download control for the checkpoint surfaces (#118). Renders nothing when the document
 *  has no subject; otherwise fetches the file through the bearer-authenticated client and hands it
 *  to the browser. Surface-agnostic — reused by Feedback and Promotion. */
export function ResumeDownload({
  subjectId,
  subjectName,
}: ResumeDownloadProps) {
  const [state, setState] = useState<keyof typeof LABELS>('idle')

  if (!subjectId) return null

  async function handleDownload() {
    if (!subjectId) return
    setState('downloading')
    try {
      await downloadResume(subjectId, `${subjectName ?? 'subject'}-resume.pdf`)
      setState('idle')
    } catch {
      setState('error')
    }
  }

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={handleDownload}
      disabled={state === 'downloading'}
    >
      {LABELS[state]}
    </Button>
  )
}
