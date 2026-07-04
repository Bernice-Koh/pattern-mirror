import { useMemo, useRef, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import {
  CATEGORY_LABELS,
  type CitedFlag,
  type DocType,
} from '@/lib/analyze-contract'
import type { DriftFinding } from '@/lib/drift-contract'
import type { ObservationItem } from '@/components/ui/observation-list'
import type { SurfaceEditorHandle } from '@/components/surface/surface-editor'
import {
  useDocumentSession,
  type DocumentSession,
} from '@/components/surface/use-document-session'
import { useDriftFindings } from '@/components/surface/use-drift-findings'
import { useFlagInteractions } from '@/components/surface/use-flag-interactions'
import type { RefObject } from 'react'

export interface CheckpointSurface {
  session: DocumentSession
  editorRef: RefObject<SurfaceEditorHandle | null>
  flags: CitedFlag[]
  setFlags: (flags: CitedFlag[]) => void
  findings: DriftFinding[]
  refetchFindings: () => void
  applyRecommendation: (flag: CitedFlag, suggestion: string) => void
  dismiss: (flagId: string) => void
  resolvedFlagIds: Set<string>
  /** The bias flags as read rows for the observations panel; resolved ones drop out at once. */
  observationItems: ObservationItem[]
  readOnly: boolean
  submitted: boolean
  isLoading: boolean
}

/** The shared logic behind the Feedback Checkpoint and Promotion Writeup surfaces: the document
 *  session, the flag set and interactions, the drift findings, and the observation rows. Both
 *  surfaces differ only in the reference context they resolve and the panels they render, so the
 *  editor/flag/drift wiring lives here once. */
export function useCheckpointSurface(docType: DocType): CheckpointSurface {
  // A document opened from My Documents (#69) arrives as ?doc=<id>; absent for a fresh draft.
  const { doc } = useSearch({ strict: false })
  const session = useDocumentSession(docType, doc)
  const editorRef = useRef<SurfaceEditorHandle>(null)
  const [flags, setFlags] = useState<CitedFlag[]>([])
  const { resolutions, accept, dismiss } = useFlagInteractions()
  const { findings, refetch } = useDriftFindings(session.documentId)

  // Apply writes the chosen phrasing into the document and logs the acceptance; marking the flag
  // resolved clears its underline at once, while the re-scan the edit triggers drops it.
  function applyRecommendation(flag: CitedFlag, suggestion: string) {
    editorRef.current?.applyRecommendation(flag, suggestion)
    accept(flag.id, suggestion)
  }

  const observationItems = useMemo(
    () =>
      flags
        .filter((flag) => !resolutions.has(flag.id))
        .map((flag) => ({
          id: flag.id,
          phrase: flag.raw_span,
          category: CATEGORY_LABELS[flag.category],
          sourceStage: flag.source_stage,
        })),
    [flags, resolutions],
  )

  const resolvedFlagIds = useMemo(
    () => new Set(resolutions.keys()),
    [resolutions],
  )

  const readOnly = session.isReadOnly
  const submitted = session.submitState === 'submitted' || readOnly

  return {
    session,
    editorRef,
    flags,
    setFlags,
    findings,
    refetchFindings: refetch,
    applyRecommendation,
    dismiss: (flagId: string) => dismiss(flagId),
    resolvedFlagIds,
    observationItems,
    readOnly,
    submitted,
    isLoading: session.isLoading,
  }
}
