import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getPromotionContext } from '@/lib/promotion-context-client'
import {
  buildRubricCoverage,
  derivePeerSynthesis,
} from '@/lib/promotion-coverage'
import { Chip } from '@/components/ui/chip'
import { CoverageList } from '@/components/ui/coverage-list'
import { InsightCallout } from '@/components/ui/insight-callout'
import { ObservationList } from '@/components/ui/observation-list'
import { CheckpointLayout } from '@/components/surface/checkpoint-layout'
import { SurfaceContextChips } from '@/components/surface/surface-context-chips'
import { useCheckpointSurface } from '@/components/surface/use-checkpoint-surface'

const SUBMIT_LABELS = {
  idle: 'Submit promotion case',
  submitting: 'Submitting…',
  submitted: 'Submitted',
  error: 'Submit promotion case',
} as const

/** Promotion Writeup (design spec §2 View 4): a promotion justification checked for bias in the
 *  language and for coverage of the target level's rubric, with what the employee's peers say set
 *  against that rubric as corroborating evidence. Reuses the shared checkpoint scaffold; net-new is
 *  the rubric bar, the peer-corroborated coverage list, and the "what peers say" panel. Drift
 *  findings are read after each run completes (#116); peer corroboration is static (#121). */
export function PromotionWriteup() {
  const surface = useCheckpointSurface('promotion')

  const context = useQuery({
    queryKey: ['promotion-context', surface.session.documentId],
    queryFn: () => {
      if (!surface.session.documentId)
        throw new Error('promotion context requires a document')
      return getPromotionContext(surface.session.documentId)
    },
    enabled: !!surface.session.documentId,
  })
  const criteria = useMemo(() => context.data?.criteria ?? [], [context.data])
  const corroboration = useMemo(
    () => context.data?.corroboration ?? [],
    [context.data],
  )

  // One coverage row per rubric criterion: the live writeup coverage joined with the static peer
  // corroboration, both anchored on the rubric so a finding's wording never has to match a peer's.
  const coverageItems = useMemo(
    () => buildRubricCoverage(criteria, surface.findings, corroboration),
    [criteria, surface.findings, corroboration],
  )

  const coverageSummary =
    surface.findings.length > 0
      ? `${coverageItems.filter((item) => !item.addressed).length} of ${coverageItems.length} not evidenced`
      : undefined

  const peerSynthesis = useMemo(
    () => derivePeerSynthesis(surface.findings, corroboration),
    [surface.findings, corroboration],
  )

  // Hold the layout until any remembered draft is restored, so the editor mounts once with its text.
  if (surface.isLoading) {
    return <main className="h-[calc(100vh-7rem)] bg-surface" />
  }

  const subBar = (
    <>
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
        title="Rubric coverage"
        summary={coverageSummary}
        items={coverageItems}
      />
      {peerSynthesis && (
        <div className="rounded-card bg-surface p-5 shadow-ring-card">
          <InsightCallout eyebrow="What peers say" lead={peerSynthesis.lead}>
            {peerSynthesis.synthesis}
          </InsightCallout>
        </div>
      )}
      <ObservationList
        title="Observations beyond the rubric"
        items={surface.observationItems}
      />
    </>
  )

  return (
    <CheckpointLayout
      surface={surface}
      documentKindLabel="Promotion writeup"
      titlePlaceholder="Untitled promotion writeup"
      subBar={subBar}
      aside={aside}
      submitLabels={SUBMIT_LABELS}
      submittedLabel="Submitted"
      footerNote="These findings are yours to weigh — submit the case whenever you’re ready."
    />
  )
}
