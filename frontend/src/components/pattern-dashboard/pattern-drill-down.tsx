import { useQuery } from '@tanstack/react-query'
import { listDocuments } from '@/lib/documents-client'
import { DocumentRow } from '@/components/pattern-dashboard/document-row'

interface PatternDrillDownProps {
  documentIds: string[]
}

/** The source documents a pattern was computed from (design spec §2 View 3 — "drill into the
 *  specific documents it came from"). Cross-references the pattern's ids against the manager's
 *  own document listing (#69) and reuses its rows, so each opens into its surface. */
export function PatternDrillDown({
  documentIds,
}: Readonly<PatternDrillDownProps>) {
  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
  })

  const ids = new Set(documentIds)
  const sources = documents.filter((document) => ids.has(document.id))

  return (
    <div className="mt-1 border-t border-border pt-3.5">
      <p className="mb-2 font-sans text-meta font-semibold text-ink-muted">
        Source documents
      </p>
      {isLoading ? (
        <p className="font-sans text-label text-ink-faint">Loading…</p>
      ) : sources.length === 0 ? (
        <p className="font-sans text-label text-ink-faint">
          Source documents are unavailable.
        </p>
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-card bg-canvas">
          {sources.map((document) => (
            <DocumentRow key={document.id} document={document} />
          ))}
        </div>
      )}
    </div>
  )
}
