import { Chip } from '@/components/ui/chip'
import { ResumeDownload } from '@/components/surface/resume-download'

interface SurfaceContextChipsProps {
  subjectName: string | null | undefined
  roleTitle: string | null | undefined
  subjectId: string | null | undefined
}

/** The right side of a checkpoint's reference bar: the subject and role chips plus the résumé
 *  download. Shared by Feedback Checkpoint and Promotion Writeup. */
export function SurfaceContextChips({
  subjectName,
  roleTitle,
  subjectId,
}: SurfaceContextChipsProps) {
  return (
    <div className="flex shrink-0 items-center gap-2">
      {subjectName && <Chip>{subjectName}</Chip>}
      {roleTitle && <Chip>{roleTitle}</Chip>}
      <ResumeDownload subjectId={subjectId} subjectName={subjectName} />
    </div>
  )
}
