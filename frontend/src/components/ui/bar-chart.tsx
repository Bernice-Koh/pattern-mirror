import type { CSSProperties, HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface BarDatum {
  label: string
  value: number
}

export interface BarChartProps extends HTMLAttributes<HTMLDivElement> {
  data?: BarDatum[]
  caption?: string
  /** Upper bound the bars and axis scale against. Defaults to the largest value shown; pass a
   *  fixed ceiling (e.g. 100 for a rate) to keep heights absolute rather than relative. */
  max?: number
  /** Format an axis tick value, e.g. `(v) => `${v}%``. Defaults to the rounded integer. */
  formatTick?: (value: number) => string
  /** Tailwind background class for the bars. @default "bg-red-primary" */
  barClassName?: string
}

const TICK_INTERVALS = 4

/** Plain vertical bar chart with a quiet y-axis: faint gridlines, solid columns, an optional
 *  caption. No tooltips. Bars and ticks scale to ``max`` or the largest value shown. */
export function BarChart({
  data = [],
  caption,
  max,
  formatTick = (value) => `${Math.round(value)}`,
  barClassName = 'bg-red-primary',
  className,
  ...props
}: Readonly<BarChartProps>) {
  const ceiling = Math.max(1, max ?? 0, ...data.map((datum) => datum.value))
  // Tick values from the ceiling down to zero, so they read top-to-bottom against the gridlines.
  const ticks = Array.from(
    { length: TICK_INTERVALS + 1 },
    (_, index) => (ceiling / TICK_INTERVALS) * (TICK_INTERVALS - index),
  )

  return (
    <div className={cn('font-sans', className)} {...props}>
      <div className="flex items-start gap-2.5">
        <div className="flex h-42 flex-col justify-between text-right text-meta text-ink-faint tabular-nums">
          {ticks.map((tick, index) => (
            <span key={index}>{formatTick(tick)}</span>
          ))}
        </div>

        <div className="flex-1">
          <div className="relative h-42">
            <div className="pointer-events-none absolute inset-0 flex flex-col justify-between">
              {ticks.map((_, index) => (
                <span key={index} className="border-t border-border" />
              ))}
            </div>
            <div className="relative flex h-full items-end gap-3.5">
              {data.map((datum) => (
                <div
                  key={datum.label}
                  className="flex h-full flex-1 items-end justify-center"
                >
                  <span
                    className={cn(
                      'h-(--bar-height) w-full max-w-12 rounded-bar',
                      barClassName,
                    )}
                    style={
                      {
                        '--bar-height': `${(datum.value / ceiling) * 100}%`,
                      } as CSSProperties
                    }
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="mt-2 flex gap-3.5">
            {data.map((datum) => (
              <span
                key={datum.label}
                className="flex-1 text-center text-meta text-ink-faint"
              >
                {datum.label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {caption && (
        <div className="mt-4 rounded-md border border-border px-3.5 py-2.5 text-body-sm text-ink">
          {caption}
        </div>
      )}
    </div>
  )
}
