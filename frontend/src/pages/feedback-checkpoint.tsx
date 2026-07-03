import { useMemo, useRef, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { CATEGORY_LABELS, type CitedFlag } from '@/lib/analyze-contract'
import { getFeedbackContext } from '@/lib/feedback-context-client'
import { Button } from '@/components/ui/button'
import { Chip } from '@/components/ui/chip'
import { CoverageList } from '@/components/ui/coverage-list'
import { Editor } from '@/components/ui/editor'
import { Legend } from '@/components/ui/legend'
import { ObservationList } from '@/components/ui/observation-list'
import { AutosaveStatus } from '@/components/surface/autosave-status'
import {
  SurfaceEditor,
  type SurfaceEditorHandle,
} from '@/components/surface/surface-editor'
import { useDocumentSession } from '@/components/surface/use-document-session'
import { useDriftFindings } from '@/components/surface/use-drift-findings'
import { useFlagInteractions } from '@/components/surface/use-flag-interactions'

const SUBMIT_LABELS = {
  idle: 'Submit to UBS systems',
  submitting: 'Submitting…',
  submitted: 'Submitted',
  error: 'Submit to UBS systems',
} as const

/** Feedback Checkpoint (design spec §2 View 2): interview feedback checked for bias in the
 *  language and for drift against the originating JD's criteria, before it is submitted. Reuses
 *  the shared editor/flag/autosave stack; net-new is the criteria bar, the coverage list, and the
 *  observations panel. Drift findings are read after each run completes (#116). */
export function FeedbackCheckpoint() {
  // A note opened from My Documents (#69) arrives as ?doc=<id>; absent for a fresh draft.
  const { doc } = useSearch({ strict: false })
  const session = useDocumentSession('feedback', doc)
  const editorRef = useRef<SurfaceEditorHandle>(null)
  const [flags, setFlags] = useState<CitedFlag[]>([])
  const { resolutions, accept, dismiss } = useFlagInteractions()
  const { findings, refetch } = useDriftFindings(session.documentId)

  const context = useQuery({
    queryKey: ['feedback-context', session.documentId],
    queryFn: () => {
      if (!session.documentId)
        throw new Error('feedback context requires a document')
      return getFeedbackContext(session.documentId)
    },
    enabled: !!session.documentId,
  })
  const criteria = useMemo(() => context.data?.criteria ?? [], [context.data])

  // Apply writes the chosen phrasing into the note and logs the acceptance; marking the flag
  // resolved clears its underline at once, while the re-scan the edit triggers drops it.
  function applyRecommendation(flag: CitedFlag, suggestion: string) {
    editorRef.current?.applyRecommendation(flag, suggestion)
    accept(flag.id, suggestion)
  }

  // Coverage renders from the drift findings once a run has produced them; before the first run
  // it shows the criteria in a neutral, not-yet-checked state so the bar is never empty.
  const coverageItems = useMemo(() => {
    if (findings.length > 0) {
      return findings.map((finding) => ({
        label: finding.criterion,
        addressed: finding.addressed,
      }))
    }
    return criteria.map((criterion) => ({
      label: criterion,
      addressed: false,
      statusLabel: 'not yet checked',
    }))
  }, [findings, criteria])

  const coverageSummary =
    findings.length > 0
      ? `${findings.filter((finding) => !finding.addressed).length} of ${findings.length} not addressed`
      : undefined

  // Observations are the bias flags — read rows here; accept/dismiss stays on the editor popover.
  // A resolved flag drops out at once, matching its cleared underline.
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

  // Hold the editor's mount until any remembered draft is restored, so it initialises once with
  // the restored text rather than flashing empty and overwriting it.
  if (session.isLoading) {
    return <main className="h-[calc(100vh-7rem)] bg-surface" />
  }

  const readOnly = session.isReadOnly
  const submitted = session.submitState === 'submitted' || readOnly

  return (
    <main className="flex h-[calc(100vh-7rem)] flex-col bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-sans text-meta text-ink-muted">
            Checking against the original JD:
          </span>
          {criteria.map((criterion) => (
            <Chip key={criterion}>{criterion}</Chip>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {context.data?.subject_name && (
            <Chip>{context.data.subject_name}</Chip>
          )}
          {context.data?.role_title && <Chip>{context.data.role_title}</Chip>}
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[58%_42%]">
        <div className="overflow-auto border-r border-border">
          <Editor
            title={session.title}
            onTitleChange={session.setTitle}
            titlePlaceholder="Untitled interview feedback"
            meta={
              <span className="inline-flex items-center gap-1.5">
                <span>
                  Interview feedback · {submitted ? 'submitted' : 'draft'}
                </span>
                {session.saveState !== 'idle' && <span aria-hidden>·</span>}
                <AutosaveStatus state={session.saveState} />
              </span>
            }
          >
            <SurfaceEditor
              ref={editorRef}
              documentId={session.documentId}
              editable={!readOnly}
              initialContent={session.initialContent}
              onTextChange={session.setContent}
              onFlagsChange={setFlags}
              onApplyRecommendation={applyRecommendation}
              onDismissFlag={(flag) => dismiss(flag.id)}
              resolvedFlagIds={resolvedFlagIds}
              onRunComplete={refetch}
            />
          </Editor>
        </div>

        <aside className="flex flex-col gap-4 overflow-auto bg-surface-alt p-5">
          <CoverageList
            title="JD criteria coverage"
            summary={coverageSummary}
            items={coverageItems}
          />
          <ObservationList
            title="Observations outside JD scope"
            items={observationItems}
          />
        </aside>
      </div>

      <footer className="border-t border-border bg-surface px-6 py-3.5">
        <div className="flex items-center justify-between">
          <span className="font-sans text-meta text-ink-muted">
            These findings are yours to weigh — submit whenever you’re ready.
          </span>
          <Button
            variant="primary"
            size="lg"
            onClick={session.submit}
            disabled={
              !session.documentId ||
              session.submitState === 'submitting' ||
              submitted
            }
          >
            {readOnly ? 'Submitted' : SUBMIT_LABELS[session.submitState]}
          </Button>
        </div>
        <div className="mt-3">
          <Legend />
        </div>
      </footer>
    </main>
  )
}
