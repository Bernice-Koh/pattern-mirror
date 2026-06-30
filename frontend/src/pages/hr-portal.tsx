import { useQuery } from '@tanstack/react-query'
import { getDictionaryHealth, getEffectiveness } from '@/lib/hr-client'
import type {
  DictionaryHealthReport,
  EffectivenessReport,
} from '@/lib/hr-contract'
import { HrHeadline } from '@/components/hr-portal/hr-headline'
import { EffectivenessTrends } from '@/components/hr-portal/effectiveness-trends'
import { DictionaryHealthPanel } from '@/components/hr-portal/dictionary-health-panel'
import {
  ReportCard,
  ReportEmptyState,
} from '@/components/hr-portal/report-card'

const EMPTY_EFFECTIVENESS: EffectivenessReport = {
  adoption_over_time: [],
  adoption_by_category: [],
  adoption_by_doc_type: [],
}

const EMPTY_DICTIONARY_HEALTH: DictionaryHealthReport = {
  proposal_volume: null,
  agent_agreement_rate: null,
  citation_coverage: null,
  approval_throughput: null,
}

/** View 4 — the HR Portal: read-only, firm-level trends over the aggregate-only query layer
 *  (#70 → #71). Firm impact and dictionary health only; no individual manager or candidate writing
 *  appears here, a boundary enforced by the data model (§5). The dictionary review queue is #72. */
export function HrPortal() {
  const effectiveness = useQuery({
    queryKey: ['hr', 'effectiveness'],
    queryFn: getEffectiveness,
  })
  const dictionaryHealth = useQuery({
    queryKey: ['hr', 'dictionary-health'],
    queryFn: getDictionaryHealth,
  })

  const report = effectiveness.data ?? EMPTY_EFFECTIVENESS

  return (
    <main className="overflow-auto bg-canvas px-10 py-9">
      <div className="mx-auto max-w-310">
        <h1 className="font-serif text-display font-bold text-ink">
          Is it working?
        </h1>
        <p className="mt-2.5 mb-7 font-sans text-body leading-relaxed text-ink-muted">
          Firm-level impact and dictionary health. No individual manager or
          candidate writing appears here.
        </p>

        <HrHeadline report={report} />

        <div className="grid grid-cols-2 gap-7">
          <EffectivenessTrends report={report} />

          <div className="flex flex-col gap-5.5">
            <ReportCard
              title="Words to review"
              caption="New bias-coded phrases waiting for review"
            >
              <ReportEmptyState message="The review queue arrives with dictionary growth" />
            </ReportCard>

            <DictionaryHealthPanel
              report={dictionaryHealth.data ?? EMPTY_DICTIONARY_HEALTH}
            />
          </div>
        </div>

        <p className="mt-7 border-t border-border pt-4 font-sans text-meta text-ink-faint">
          Aggregated trends only. No individual manager or candidate writing is
          shown here — enforced by the data model, not by policy.
        </p>
      </div>
    </main>
  )
}
