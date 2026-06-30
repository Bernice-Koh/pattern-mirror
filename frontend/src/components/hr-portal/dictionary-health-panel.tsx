import type { ReactNode } from 'react'
import type { DictionaryHealthReport } from '@/lib/hr-contract'
import {
  ReportCard,
  ReportEmptyState,
} from '@/components/hr-portal/report-card'

interface DictionaryHealthPanelProps {
  report: DictionaryHealthReport
}

function HealthStat({
  value,
  label,
}: Readonly<{ value: ReactNode; label: string }>) {
  return (
    <div>
      <div className="font-sans text-metric-sm font-semibold text-ink">
        {value}
      </div>
      <div className="mt-1.5 font-sans text-meta text-ink-faint">{label}</div>
    </div>
  )
}

function percent(rate: number | null): string {
  return rate === null ? '—' : `${Math.round(rate * 100)}%`
}

function count(value: number | null): string {
  return value === null ? '—' : value.toString()
}

/** The dictionary-health card (#71, design spec §11): proposal volume, agent-agreement rate,
 *  citation coverage, and approval throughput. Empty until Dictionary Growth (#8) provides data. */
export function DictionaryHealthPanel({
  report,
}: Readonly<DictionaryHealthPanelProps>) {
  const empty =
    report.proposal_volume === null &&
    report.agent_agreement_rate === null &&
    report.citation_coverage === null &&
    report.approval_throughput === null

  return (
    <ReportCard title="Dictionary health">
      {empty ? (
        <ReportEmptyState message="Dictionary health appears once the dictionary starts growing" />
      ) : (
        <div className="grid grid-cols-2 gap-x-6 gap-y-5">
          <HealthStat
            value={count(report.proposal_volume)}
            label="candidate words this month"
          />
          <HealthStat
            value={percent(report.agent_agreement_rate)}
            label="average agent agreement"
          />
          <HealthStat
            value={percent(report.citation_coverage)}
            label="backed by a citation"
          />
          <HealthStat
            value={count(report.approval_throughput)}
            label="approved this period"
          />
        </div>
      )}
    </ReportCard>
  )
}
