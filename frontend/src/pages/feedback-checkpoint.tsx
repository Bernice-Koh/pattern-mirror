import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getFeedbackContext } from '@/lib/feedback-context-client'
import { Chip } from '@/components/ui/chip'
import { CoverageList } from '@/components/ui/coverage-list'
import { ObservationList } from '@/components/ui/observation-list'
import { CheckpointLayout } from '@/components/surface/checkpoint-layout'
import { SurfaceContextChips } from '@/components/surface/surface-context-chips'
import { useCheckpointSurface } from '@/components/surface/use-checkpoint-surface'

const SUBMIT_LABELS = {
  idle: 'Submit to UBS systems',
  submitting: 'Submitting…',
  submitted: 'Submitted',
  error: 'Submit to UBS systems',
} as const

/** Feedback Checkpoint (design spec §2 View 2): interview feedback checked for bias in the
 *  language and for drift against the originating JD's criteria, before it is submitted. Reuses the
 *  shared checkpoint scaffold; net-new is the criteria bar, the coverage list, and the observations
 *  panel. Drift findings are read after each run completes (#116). */
export function FeedbackCheckpoint() {
  const surface = useCheckpointSurface('feedback')

  const context = useQuery({
    queryKey: ['feedback-context', surface.session.documentId],
    queryFn: () => {
      if (!surface.session.documentId)
        throw new Error('feedback context requires a document')
      return getFeedbackContext(surface.session.documentId)
    },
    enabled: !!surface.session.documentId,
  })
  const criteria = useMemo(() => context.data?.criteria ?? [], [context.data])

  // Coverage renders from the drift findings once a run has produced them; before the first run it
  // shows the criteria in a neutral, not-yet-checked state so the bar is never empty.
  const coverageItems = useMemo(() => {
    if (surface.findings.length > 0) {
      return surface.findings.map((finding) => ({
        label: finding.criterion,
        addressed: finding.addressed,
      }))
    }
    return criteria.map((criterion) => ({
      label: criterion,
      addressed: false,
      statusLabel: 'not yet checked',
    }))
  }, [surface.findings, criteria])

  const coverageSummary =
    surface.findings.length > 0
      ? `${surface.findings.filter((finding) => !finding.addressed).length} of ${surface.findings.length} not addressed`
      : undefined

  // Hold the layout until any remembered draft is restored, so the editor mounts once with its text.
  if (surface.isLoading) {
    return <main className="h-[calc(100vh-7rem)] bg-surface" />
  }

  const subBar = (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-sans text-meta text-ink-muted">
          Checking against the original JD:
        </span>
        {criteria.map((criterion) => (
          <Chip key={criterion}>{criterion}</Chip>
        ))}
      </div>
      <SurfaceContextChips
        subjectName={context.data?.subject_name}
        roleTitle={context.data?.role_title}
        subjectId={context.data?.subject_id}
      />
    </>
  )

  const aside = (
    <>
      <CoverageList
        title="JD criteria coverage"
        summary={coverageSummary}
        items={coverageItems}
      />
      <ObservationList
        title="Observations outside JD scope"
        items={surface.observationItems}
      />
    </>
  )

  return (
    <CheckpointLayout
      surface={surface}
      documentKindLabel="Interview feedback"
      titlePlaceholder="Untitled interview feedback"
      subBar={subBar}
      aside={aside}
      submitLabels={SUBMIT_LABELS}
      submittedLabel="Submitted"
      footerNote="These findings are yours to weigh — submit whenever you’re ready."
    />
  )
}
