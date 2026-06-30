import { useNavigate } from '@tanstack/react-router'
import type { DocType } from '@/lib/analyze-contract'
import type { DocumentSummary } from '@/lib/documents-contract'

const ROUTE_BY_TYPE: Record<
  DocType,
  '/jd-studio' | '/feedback-checkpoint' | '/promotion-writeup'
> = {
  jd: '/jd-studio',
  feedback: '/feedback-checkpoint',
  promotion: '/promotion-writeup',
}

const UNTITLED: Record<DocType, string> = {
  jd: 'Untitled job description',
  feedback: 'Untitled feedback',
  promotion: 'Untitled promotion writeup',
}

// JDs are "published", the checkpoints are "submitted" — the mockup's own wording.
const SUBMITTED_VERB: Record<DocType, string> = {
  jd: 'Published',
  feedback: 'Submitted',
  promotion: 'Submitted',
}

function formatDay(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
  }).format(new Date(iso))
}

function metaLine(document: DocumentSummary): string {
  const role = document.role_title
  if (document.status === 'draft') return role ? `Draft · ${role}` : 'Draft'
  const when = formatDay(document.submitted_at ?? document.created_at)
  const lead = `${SUBMITTED_VERB[document.doc_type]} ${when}`
  return role ? `${lead} · ${role}` : lead
}

interface DocumentRowProps {
  document: DocumentSummary
}

/** One row in My Documents; opens the document in its surface on click (#69). */
export function DocumentRow({ document }: DocumentRowProps) {
  const navigate = useNavigate()
  const title = document.title ?? UNTITLED[document.doc_type]

  return (
    <button
      type="button"
      onClick={() =>
        navigate({
          to: ROUTE_BY_TYPE[document.doc_type],
          search: { doc: document.id },
        })
      }
      className="flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-canvas"
    >
      <span className="flex-1">
        <span className="block font-sans text-body-sm font-semibold text-ink">
          {title}
        </span>
        <span className="mt-0.5 block font-sans text-label text-ink-faint">
          {metaLine(document)}
        </span>
      </span>
      <span aria-hidden className="font-sans text-body-sm text-ink-faint">
        →
      </span>
    </button>
  )
}
