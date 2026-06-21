import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface LegendProps extends HTMLAttributes<HTMLDivElement> {
  showDismissed?: boolean
}

/** Inline-flag key: pairs each colour with its underline style and a text label. */
export function Legend({
  showDismissed = false,
  className,
  ...props
}: LegendProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-7 font-sans text-micro text-ink-faint',
        className,
      )}
      {...props}
    >
      <span className="inline-flex items-center gap-2.5">
        <span className="inline-block w-6 border-b-2 border-red-line" />
        solid red — dictionary flag
      </span>
      <span className="inline-flex items-center gap-2.5">
        <span className="inline-block w-6 border-b-2 border-dashed border-amber-line" />
        dashed amber — AI contextual flag
      </span>
      {showDismissed && (
        <span className="inline-flex items-center gap-2.5">
          <span className="line-through opacity-60">abc</span>
          strikethrough — dismissed (still logged)
        </span>
      )}
    </div>
  )
}
