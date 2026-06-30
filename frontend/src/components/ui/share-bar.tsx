import type { CSSProperties } from 'react'
import { cn } from '@/lib/cn'

export interface ShareBarProps {
  label: string
  /** A 0–1 proportion, rendered as a track-filling bar and a percentage. */
  value: number
  /** Tailwind background class for the fill (and the dot, when shown). @default "bg-red-primary" */
  color?: string
  /** Show a leading dot in the fill colour, for a colour-keyed legend. @default false */
  showDot?: boolean
}

/** A labelled horizontal proportion row: an optional colour dot, a name, a track-filling bar, and
 *  the percentage. The HR Portal's categorical breakdowns (#71) — share of flags by document type
 *  (plain) and by characteristic (colour-keyed with a dot). */
export function ShareBar({
  label,
  value,
  color = 'bg-red-primary',
  showDot = false,
}: Readonly<ShareBarProps>) {
  const percent = Math.round(value * 100)
  return (
    <div className="grid grid-cols-[170px_1fr_44px] items-center gap-3.5 py-2 font-sans">
      <span className="flex items-center gap-2.5 text-body-sm text-ink">
        {showDot && (
          <span className={cn('size-2.5 flex-none rounded-full', color)} />
        )}
        {label}
      </span>
      <span className="h-2.5 rounded-full bg-chip-track">
        <span
          className={cn('block h-full w-(--share-width) rounded-full', color)}
          style={{ '--share-width': `${percent}%` } as CSSProperties}
        />
      </span>
      <span className="text-right text-body-sm text-ink-muted tabular-nums">
        {percent}%
      </span>
    </div>
  )
}
