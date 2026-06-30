import { type ReactNode } from 'react'
import type {
  CategoryImprovement,
  FlagVolumePoint,
} from '@/lib/patterns-contract'
import { categoryLabel, periodLabel } from '@/lib/pattern-format'
import { BarChart, type BarDatum } from '@/components/ui/bar-chart'

interface WritingVolumeTrendsProps {
  flagVolume: FlagVolumePoint[]
  improvements: CategoryImprovement[]
}

function Panel({
  title,
  caption,
  children,
}: Readonly<{ title: string; caption: string; children: ReactNode }>) {
  return (
    <div className="rounded-card bg-surface p-6 shadow-ring-card">
      <h3 className="font-sans text-subheading font-semibold text-ink">
        {title}
      </h3>
      <p className="mt-0.5 mb-4 font-sans text-label text-ink-faint">
        {caption}
      </p>
      {children}
    </div>
  )
}

function EmptyState({ message }: Readonly<{ message: string }>) {
  return (
    <div className="flex h-42 items-center justify-center rounded-md border border-dashed border-border">
      <span className="font-sans text-body-sm text-ink-faint">{message}</span>
    </div>
  )
}

function formatRate(rate: number): string {
  return rate.toFixed(1)
}

/** A factual first-to-last delta caption; undefined until there are two periods to compare. */
function volumeCaption(trend: FlagVolumePoint[]): string | undefined {
  if (trend.length < 2) return undefined
  const first = trend[0]
  const last = trend.at(-1) ?? first
  return `Your average flags per document went from ${formatRate(
    first.flags_per_document,
  )} in ${periodLabel(first.period)} to ${formatRate(
    last.flags_per_document,
  )} in ${periodLabel(last.period)}.`
}

/** View 3 — the manager's own writing-volume trends (design spec §2 View 3, #99): how much flagged
 *  language their writing carries over time, and the categories where it has fallen most. About flag
 *  counts, not decisions (#68). Descriptive, not significance-gated; visible only to the manager. */
export function WritingVolumeTrends({
  flagVolume,
  improvements,
}: Readonly<WritingVolumeTrendsProps>) {
  const volumeBars: BarDatum[] = flagVolume.map((point) => ({
    label: periodLabel(point.period),
    value: point.flags_per_document,
  }))
  const improvementBars: BarDatum[] = improvements.map((improvement) => ({
    label: categoryLabel(improvement.category),
    value: Math.round((improvement.reduction / improvement.first_rate) * 100),
  }))

  return (
    <div className="mb-7 grid grid-cols-[1.2fr_1fr] gap-5.5">
      <Panel
        title="Bias flags over time"
        caption="Average flags per document, over time"
      >
        {flagVolume.length > 0 ? (
          <BarChart
            data={volumeBars}
            formatTick={formatRate}
            caption={volumeCaption(flagVolume)}
          />
        ) : (
          <EmptyState message="Not enough history yet" />
        )}
      </Panel>

      <Panel
        title="Where you've improved"
        caption="Reduction in flagged language, by category"
      >
        {improvements.length > 0 ? (
          <BarChart
            data={improvementBars}
            max={100}
            formatTick={(value) => `${value}%`}
            barClassName="bg-green-positive"
          />
        ) : (
          <EmptyState message="No category trends yet" />
        )}
      </Panel>
    </div>
  )
}
