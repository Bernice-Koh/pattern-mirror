import type { BiasCategory } from '@/lib/patterns-contract'
import type { EffectivenessReport } from '@/lib/hr-contract'
import { categoryLabel, docTypeLabel, periodLabel } from '@/lib/pattern-format'
import {
  flagVolumeDrop,
  flagVolumeOverTime,
  shareByCategory,
  shareByDocType,
} from '@/lib/hr-metrics'
import { BarChart, type BarDatum } from '@/components/ui/bar-chart'
import { ShareBar } from '@/components/ui/share-bar'
import {
  ReportCard,
  ReportEmptyState,
} from '@/components/hr-portal/report-card'

interface EffectivenessTrendsProps {
  report: EffectivenessReport
}

/** WFA characteristic colour per bias category, in lockstep with the manager surfaces' palette. */
const CATEGORY_COLOR: Record<BiasCategory, string> = {
  gender: 'bg-wfa-sex',
  age: 'bg-wfa-age',
  nationality: 'bg-wfa-nationality',
  race: 'bg-wfa-race',
  disability: 'bg-wfa-disability',
  family_status: 'bg-wfa-caregiving',
  relevance: 'bg-wfa-other',
}

/** A factual "down X% since <first month>" line; undefined until there are two months to compare. */
function volumeCaption(report: EffectivenessReport): string | undefined {
  const drop = flagVolumeDrop(report)
  if (drop === null || drop === 0) return undefined
  const firstMonth = periodLabel(report.adoption_over_time[0].period)
  const magnitude = Math.abs(Math.round(drop * 100))
  const direction = drop > 0 ? 'Down' : 'Up'
  return `${direction} ${magnitude}% firm-wide since ${firstMonth}.`
}

/** The effectiveness dimension (#71, design spec §11): firm-wide bias-flag volume over time and two
 *  share-of-flags breakdowns — by document type and by characteristic. */
export function EffectivenessTrends({
  report,
}: Readonly<EffectivenessTrendsProps>) {
  const volumeBars: BarDatum[] = flagVolumeOverTime(report).map((point) => ({
    label: periodLabel(point.period),
    value: point.flag_count,
  }))
  const docTypeShares = shareByDocType(report)
  const categoryShares = shareByCategory(report)

  return (
    <div className="flex flex-col gap-5.5">
      <ReportCard
        title="Bias flags raised over time"
        caption="Firm-wide, by month"
      >
        {volumeBars.length > 0 ? (
          <BarChart
            data={volumeBars}
            integerTicks
            caption={volumeCaption(report)}
          />
        ) : (
          <ReportEmptyState message="Not enough history yet" />
        )}
      </ReportCard>

      <ReportCard
        title="Where bias appears most"
        caption="Share of all bias flags, by document type"
      >
        {docTypeShares.length > 0 ? (
          docTypeShares.map((row) => (
            <ShareBar
              key={row.doc_type}
              label={docTypeLabel(row.doc_type)}
              value={row.share}
            />
          ))
        ) : (
          <ReportEmptyState message="No document-type data yet" />
        )}
      </ReportCard>

      <ReportCard
        title="Most-flagged characteristics"
        caption="Share of bias flags, by characteristic"
      >
        {categoryShares.length > 0 ? (
          categoryShares.map((row) => (
            <ShareBar
              key={row.category}
              label={categoryLabel(row.category)}
              value={row.share}
              color={CATEGORY_COLOR[row.category]}
              showDot
            />
          ))
        ) : (
          <ReportEmptyState message="No characteristic data yet" />
        )}
      </ReportCard>
    </div>
  )
}
