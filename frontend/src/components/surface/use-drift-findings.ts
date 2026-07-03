import { useQuery } from '@tanstack/react-query'
import { listDriftFindings } from '@/lib/drift-client'
import type { DriftFinding } from '@/lib/drift-contract'

/** Read a document's drift findings (its criteria coverage). A request/response read, so it lives
 *  on TanStack Query rather than the accumulating flag-stream hook (CODE_STYLE: state management).
 *  The surface calls `refetch` after a run completes, once the backend has persisted the latest
 *  findings — they are read after the stream's `done` event, not streamed (#116). */
export function useDriftFindings(documentId: string | null): {
  findings: DriftFinding[]
  refetch: () => void
} {
  const query = useQuery({
    queryKey: ['drift-findings', documentId],
    queryFn: () => {
      if (!documentId) throw new Error('drift findings require a document')
      return listDriftFindings(documentId)
    },
    enabled: !!documentId,
  })

  return { findings: query.data ?? [], refetch: () => void query.refetch() }
}
