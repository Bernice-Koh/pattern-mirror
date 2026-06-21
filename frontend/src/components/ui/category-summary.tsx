import type { CSSProperties, HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface CategoryCount {
  label: string
  count: number
  /** Tailwind background class for the bar fill. @default "bg-red-primary" */
  barClassName?: string
}

export interface CategorySummaryProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  items?: CategoryCount[]
  note?: string
}

/** Per-category counts as a horizontal bar graph — observations, not a score. */
export function CategorySummary({
  title = 'This document',
  items = [],
  note = 'Observations, not a score — you decide what to change.',
  className,
  ...props
}: CategorySummaryProps) {
  const max = Math.max(1, ...items.map((item) => item.count))

  return (
    <div className={cn('font-sans', className)} {...props}>
      {title && <p className="mb-3 text-meta text-ink-muted">{title}</p>}
      <div className="flex flex-col gap-2.5">
        {items.map((item) => (
          <div
            key={item.label}
            className="grid grid-cols-[92px_1fr_18px] items-center gap-3"
          >
            <span className="text-label text-ink-muted">{item.label}</span>
            <span className="block h-2 overflow-hidden rounded bg-chip-track">
              <span
                className={cn(
                  'block h-full w-(--bar-fill) rounded',
                  item.barClassName ?? 'bg-red-primary',
                )}
                style={
                  {
                    '--bar-fill': `${(item.count / max) * 100}%`,
                  } as CSSProperties
                }
              />
            </span>
            <span className="text-right text-label text-ink-muted">
              {item.count}
            </span>
          </div>
        ))}
      </div>
      {note && <p className="mt-3.5 text-meta text-ink-faint italic">{note}</p>}
    </div>
  )
}
