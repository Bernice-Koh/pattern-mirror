import { useMemo, useRef, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { CATEGORY_LABELS, type CitedFlag } from '@/lib/analyze-contract'
import { getPromotionContext } from '@/lib/promotion-context-client'
import {
  buildRubricCoverage,
  derivePeerSynthesis,
} from '@/lib/promotion-coverage'
import { Button } from '@/components/ui/button'
import { Chip } from '@/components/ui/chip'
import { CoverageList } from '@/components/ui/coverage-list'
import { Editor } from '@/components/ui/editor'
import { InsightCallout } from '@/components/ui/insight-callout'
import { Legend } from '@/components/ui/legend'
import { ObservationList } from '@/components/ui/observation-list'
import { AutosaveStatus } from '@/components/surface/autosave-status'
import { ResumeDownload } from '@/components/surface/resume-download'
import {
  SurfaceEditor,
  type SurfaceEditorHandle,
} from '@/components/surface/surface-editor'
import { useDocumentSession } from '@/components/surface/use-document-session'
import { useDriftFindings } from '@/components/surface/use-drift-findings'
import { useFlagInteractions } from '@/components/surface/use-flag-interactions'

const SUBMIT_LABELS = {
  idle: 'Submit promotion case',
  submitting: 'Submitting…',
  submitted: 'Submitted',
  error: 'Submit promotion case',
} as const

/** Promotion Writeup (design spec §2 View 4): a promotion justification checked for bias in the
 *  language and for coverage of the target level's rubric, with what the employee's peers say set
 *  against that rubric as corroborating evidence. Reuses the shared editor/flag/autosave stack;
 *  net-new is the rubric bar, the peer-corroborated coverage list, and the "what peers say" panel.
 *  Drift findings are read after each run completes (#116); peer corroboration is static (#121). */
export function PromotionWriteup() {
  // A writeup opened from My Documents (#69) arrives as ?doc=<id>; absent for a fresh draft.
  const { doc } = useSearch({ strict: false })
  const session = useDocumentSession('promotion', doc)
  const editorRef = useRef<SurfaceEditorHandle>(null)
  const [flags, setFlags] = useState<CitedFlag[]>([])
  const { resolutions, accept, dismiss } = useFlagInteractions()
  const { findings, refetch } = useDriftFindings(session.documentId)

  const context = useQuery({
    queryKey: ['promotion-context', session.documentId],
    queryFn: () => {
      if (!session.documentId)
        throw new Error('promotion context requires a document')
      return getPromotionContext(session.documentId)
    },
    enabled: !!session.documentId,
  })
  const criteria = useMemo(() => context.data?.criteria ?? [], [context.data])
  const corroboration = useMemo(
    () => context.data?.corroboration ?? [],
    [context.data],
  )

  // Apply writes the chosen phrasing into the writeup and logs the acceptance; marking the flag
  // resolved clears its underline at once, while the re-scan the edit triggers drops it.
  function applyRecommendation(flag: CitedFlag, suggestion: string) {
    editorRef.current?.applyRecommendation(flag, suggestion)
    accept(flag.id, suggestion)
  }

  // One coverage row per rubric criterion: the live writeup coverage joined with the static peer
  // corroboration, both anchored on the rubric so a finding's wording never has to match a peer's.
  const coverageItems = useMemo(
    () => buildRubricCoverage(criteria, findings, corroboration),
    [criteria, findings, corroboration],
  )

  const coverageSummary =
    findings.length > 0
      ? `${coverageItems.filter((item) => !item.addressed).length} of ${coverageItems.length} not evidenced`
      : undefined

  const peerSynthesis = useMemo(
    () => derivePeerSynthesis(findings, corroboration),
    [findings, corroboration],
  )

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
            {context.data?.role_title
              ? `Checking against the ${context.data.role_title} rubric:`
              : 'Checking against the promotion rubric:'}
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
          <ResumeDownload
            subjectId={context.data?.subject_id}
            subjectName={context.data?.subject_name}
          />
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[58%_42%]">
        <div className="overflow-auto border-r border-border">
          <Editor
            title={session.title}
            onTitleChange={session.setTitle}
            titlePlaceholder="Untitled promotion writeup"
            meta={
              <span className="inline-flex items-center gap-1.5">
                <span>
                  Promotion writeup · {submitted ? 'submitted' : 'draft'}
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
            title="Rubric coverage"
            summary={coverageSummary}
            items={coverageItems}
          />
          {peerSynthesis && (
            <div className="rounded-card bg-surface p-5 shadow-ring-card">
              <InsightCallout
                eyebrow="What peers say"
                lead={peerSynthesis.lead}
              >
                {peerSynthesis.synthesis}
              </InsightCallout>
            </div>
          )}
          <ObservationList
            title="Observations beyond the rubric"
            items={observationItems}
          />
        </aside>
      </div>

      <footer className="border-t border-border bg-surface px-6 py-3.5">
        <div className="flex items-center justify-between">
          <span className="font-sans text-meta text-ink-muted">
            These findings are yours to weigh — submit the case whenever you’re
            ready.
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
