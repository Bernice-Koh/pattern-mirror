import type {
  AdoptionTrendPoint,
  DecisionPattern,
} from '@/lib/patterns-contract'
import { periodLabel, yearSpanLabel } from '@/lib/pattern-format'
import { BarChart, type BarDatum } from '@/components/ui/bar-chart'
import { BehaviouralPatternCard } from '@/components/pattern-dashboard/behavioural-pattern-card'

interface BehaviouralReflectionProps {
  patterns: DecisionPattern[]
  trend: AdoptionTrendPoint[]
}

function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`
}

/** A factual first-to-last delta caption; undefined until there are two periods to compare. */
function trendCaption(trend: AdoptionTrendPoint[]): string | undefined {
  if (trend.length < 2) return undefined
  const first = trend[0]
  const last = trend.at(-1) ?? first
  return `Your adoption rate went from ${percent(first.adoption_rate)} in ${periodLabel(
    first.period,
  )} to ${percent(last.adoption_rate)} in ${periodLabel(last.period)}.`
}

/** View 3 Layer 2 — behavioural reflection (design spec §13). The manager's own decisions about
 *  flags: an adoption-rate trend over time and the categories they adopt or reject at a
 *  significantly different rate. Presented without editorialising — they draw the conclusion. */
export function BehaviouralReflection({
  patterns,
  trend,
}: Readonly<BehaviouralReflectionProps>) {
  const bars: BarDatum[] = trend.map((point) => ({
    label: periodLabel(point.period),
    value: Math.round(point.adoption_rate * 100),
  }))

  return (
    <section className="mb-7">
      <h2 className="mb-1 font-sans text-body-sm font-semibold text-ink-muted">
        How you&apos;ve responded to flags
      </h2>
      <p className="mb-4 max-w-165 font-sans text-label text-ink-faint">
        Your own decisions about the language the tool flagged — visible only to
        you.
      </p>

      {trend.length > 0 && (
        <div className="mb-6 rounded-card bg-surface p-6 shadow-ring-card">
          <h3 className="font-sans text-subheading font-semibold text-ink">
            Adoption rate over time
          </h3>
          <p className="mt-0.5 mb-4 font-sans text-label text-ink-faint">
            Share of flagged language you revised, by month
          </p>
          <BarChart
            data={bars}
            max={100}
            formatTick={(value) => `${value}%`}
            barClassName="bg-green-positive"
            caption={trendCaption(trend)}
          />
          <p className="mt-2 text-center font-sans text-meta text-ink-faint">
            {yearSpanLabel(trend.map((point) => point.period))}
          </p>
        </div>
      )}

      {patterns.length > 0 ? (
        <div className="grid grid-cols-2 gap-5">
          {patterns.map((pattern) => (
            <BehaviouralPatternCard key={pattern.category} pattern={pattern} />
          ))}
        </div>
      ) : (
        <p className="rounded-card bg-surface p-5 font-sans text-body-sm text-ink-muted shadow-ring-card">
          No clear patterns in your decisions yet. Patterns appear here only
          once they are unlikely to be a coincidence.
        </p>
      )}
    </section>
  )
}
