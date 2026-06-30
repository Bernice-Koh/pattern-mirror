import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { DocType } from '@/lib/analyze-contract'
import { listDocuments } from '@/lib/documents-client'
import { DocumentRow } from '@/components/pattern-dashboard/document-row'

const TABS: { label: string; type: DocType }[] = [
  { label: 'JD', type: 'jd' },
  { label: 'Feedback', type: 'feedback' },
  { label: 'Promotion', type: 'promotion' },
]

/** The manager's document history (design spec §2 View 3): their own JDs, feedback, and
 *  promotion writeups, filtered by type. Scoping to the owner is the backend's job (#69) —
 *  this view only renders what the listing returns. */
export function MyDocuments() {
  const [activeType, setActiveType] = useState<DocType>('jd')
  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
  })

  const visible = documents.filter(
    (document) => document.doc_type === activeType,
  )

  let listing: ReactNode
  if (isLoading) {
    listing = (
      <p className="px-4 py-6 font-sans text-label text-ink-faint">Loading…</p>
    )
  } else if (visible.length === 0) {
    listing = (
      <p className="px-4 py-6 font-sans text-label text-ink-faint">
        Nothing here yet.
      </p>
    )
  } else {
    listing = (
      <div className="divide-y divide-border">
        {visible.map((document) => (
          <DocumentRow key={document.id} document={document} />
        ))}
      </div>
    )
  }

  return (
    <div className="max-w-225">
      <h1 className="font-serif text-display font-bold text-ink">
        My documents
      </h1>
      <p className="mt-2.5 mb-6 font-sans text-body leading-relaxed text-ink-muted">
        Everything you&apos;ve written through Pattern Mirror. Open any document
        to review the saved version.
      </p>

      <div className="mb-1 flex gap-1 border-b border-border">
        {TABS.map((tab) => {
          const active = tab.type === activeType
          return (
            <button
              key={tab.type}
              type="button"
              onClick={() => setActiveType(tab.type)}
              className={`-mb-px border-b-2 px-3.5 py-2.5 font-sans text-body-sm transition-colors ${
                active
                  ? 'border-red-primary font-semibold text-ink'
                  : 'border-transparent text-ink-muted'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      <div className="overflow-hidden rounded-card bg-surface shadow-ring-card">
        {listing}
      </div>

      <p className="mt-4 font-sans text-meta text-ink-faint">
        A document lands here after you publish it in JD Studio or submit it at
        a checkpoint. This is your own data — visible only to you.
      </p>
    </div>
  )
}
