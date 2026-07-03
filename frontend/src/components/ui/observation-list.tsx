import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import type { FlagSourceStage } from '@/lib/analyze-contract'
import { Badge } from '@/components/ui/badge'

export interface ObservationItem {
  id: string
  phrase: string
  /** Canonical bias-category label (from CATEGORY_LABELS). */
  category: string
  sourceStage: FlagSourceStage
}

export interface ObservationListProps extends HTMLAttributes<HTMLDivElement> {
  /** Card heading. @default "Observations" */
  title?: string
  items: ObservationItem[]
}

const DOT_BY_STAGE: Record<FlagSourceStage, string> = {
  contextual: 'bg-amber-contextual',
  dictionary: 'bg-red-primary',
}

/** Bias observations that fall outside the reference criteria — a compact read row per flag
 *  (dot by stage, phrase, canonical category). Actioning stays on the inline editor popover;
 *  this panel only reflects what the engine surfaced. */
export function ObservationList({
  title = 'Observations',
  items,
  className,
  ...props
}: ObservationListProps) {
  return (
    <div
      className={cn(
        'rounded-card bg-surface p-5 font-sans shadow-ring-card',
        className,
      )}
      {...props}
    >
      <div className="mb-1.5 flex items-center justify-between">
        <h3 className="font-sans text-subheading font-semibold text-ink">
          {title}
        </h3>
        <Badge tone="neutral">{items.length} found</Badge>
      </div>
      {items.length === 0 ? (
        <p className="py-2 text-label text-ink-faint">
          Nothing flagged outside the criteria.
        </p>
      ) : (
        <div className="flex flex-col">
          {items.map((item, index) => (
            <div
              key={item.id}
              className={cn(
                'flex items-center gap-3 py-3',
                index > 0 && 'border-t border-border',
              )}
            >
              <span
                aria-hidden
                className={cn(
                  'size-2 shrink-0 rounded-full',
                  DOT_BY_STAGE[item.sourceStage],
                )}
              />
              <span className="flex-1 text-label text-ink">{item.phrase}</span>
              <span className="text-meta text-ink-faint">{item.category}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
