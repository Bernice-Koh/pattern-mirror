import type { ReactNode } from 'react'
import type { EffectivenessReport } from '@/lib/hr-contract'
import { periodLabel } from '@/lib/pattern-format'
import { flagVolumeDrop, overallAdoptionRate } from '@/lib/hr-metrics'

interface HrHeadlineProps {
  report: EffectivenessReport
}

const PENDING = '—'

function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

function StatCard({
  label,
  value,
  delta,
}: Readonly<{ label: string; value: ReactNode; delta: string }>) {
  return (
    <div className="flex flex-col gap-2.5 rounded-card bg-surface px-5 py-5 font-sans shadow-ring-card">
      <span className="text-body-sm text-ink-muted">{label}</span>
      <span className="text-metric-sm font-semibold text-ink">{value}</span>
      <span className="text-meta text-ink-faint">{delta}</span>
    </div>
  )
}

/** A plain-language firm-level summary, built only from figures that are actually available. */
function summaryText(report: EffectivenessReport): string {
  const drop = flagVolumeDrop(report)
  const adoption = overallAdoptionRate(report)
  const clauses: string[] = []
  if (drop !== null && drop !== 0) {
    const firstMonth = periodLabel(report.adoption_over_time[0].period)
    const direction = drop > 0 ? 'down' : 'up'
    clauses.push(
      `bias-coded language across the firm is ${direction} ${Math.abs(
        Math.round(drop * 100),
      )}% since ${firstMonth}`,
    )
  }
  if (adoption !== null) {
    clauses.push(
      `managers revise ${percent(adoption)} of flagged language before submitting`,
    )
  }
  if (clauses.length === 0) {
    return "Firm-level impact will appear here as the firm's history grows."
  }
  const sentence = clauses.join(', and ')
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}.`
}

/** The HR Portal headline (design spec §11): four firm-level stat cards and a plain-language
 *  summary. Bias-coded-language drop and revision rate come from the effectiveness aggregate (#70);
 *  recurring-habit and document counts are pending until their aggregates exist. */
export function HrHeadline({ report }: Readonly<HrHeadlineProps>) {
  const drop = flagVolumeDrop(report)
  const adoption = overallAdoptionRate(report)

  return (
    <>
      <div className="mb-6 grid grid-cols-2 gap-4.5">
        <StatCard
          label="Bias-coded language"
          value={
            drop !== null && drop !== 0 ? (
              <>
                <span
                  className={
                    drop > 0 ? 'text-green-positive' : 'text-red-primary'
                  }
                >
                  {drop > 0 ? '↓' : '↑'}
                </span>{' '}
                {Math.abs(Math.round(drop * 100))}%
              </>
            ) : (
              PENDING
            )
          }
          delta="firm-wide this year"
        />
        <StatCard
          label="Flagged language revised"
          value={adoption !== null ? percent(adoption) : PENDING}
          delta="before submission this year"
        />
      </div>

      <div className="mb-7 rounded-card bg-surface p-6 shadow-ring-card">
        <div className="mb-3 font-sans text-body-sm font-semibold text-ink-muted">
          Summary
        </div>
        <p className="font-sans text-body leading-relaxed text-ink">
          {summaryText(report)}
        </p>
      </div>
    </>
  )
}
