import type { CSSProperties, HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface BarDatum {
  label: string
  value: number
}

export interface BarChartProps extends HTMLAttributes<HTMLDivElement> {
  data?: BarDatum[]
  caption?: string
  /** Upper bound the bars scale against. Defaults to the largest value shown; pass a fixed
   *  ceiling (e.g. 100 for a rate) to keep heights absolute rather than relative. */
  max?: number
  /** Tailwind background class for the bars. @default "bg-red-primary" */
  barClassName?: string
}

/** Plain vertical bar chart — solid columns, a faint axis, an optional caption. No gridlines,
 *  no tooltips; honest and quiet, per the design kit. Bars scale to ``max`` or the largest value. */
export function BarChart({
  data = [],
  caption,
  max,
  barClassName = 'bg-red-primary',
  className,
  ...props
}: BarChartProps) {
  const ceiling = Math.max(1, max ?? 0, ...data.map((datum) => datum.value))

  return (
    <div className={cn('font-sans', className)} {...props}>
      <div className="flex h-42 items-end gap-3.5">
        {data.map((datum) => (
          <div
            key={datum.label}
            className="flex h-full flex-1 flex-col items-center justify-end gap-2.5"
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
            <span className="text-meta text-ink-faint">{datum.label}</span>
          </div>
        ))}
      </div>
      {caption && (
        <div className="mt-4 rounded-md border border-border px-3.5 py-2.5 text-body-sm text-ink">
          {caption}
        </div>
      )}
    </div>
  )
}
