import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface InsightCalloutProps extends HTMLAttributes<HTMLDivElement> {
  /** Red uppercase label above the lead, e.g. "What peers say". */
  eyebrow?: string
  /** Framing paragraph shown above the emphasised takeaway. */
  lead?: ReactNode
  /** The emphasised takeaway, rendered in the tinted box. */
  children: ReactNode
}

/** A framed insight: a red eyebrow, a lead paragraph, and an emphasised takeaway in a tinted box.
 *  The Promotion Writeup's "what peers say" panel — peer feedback set against the rubric. */
export function InsightCallout({
  eyebrow,
  lead,
  children,
  className,
  ...props
}: InsightCalloutProps) {
  return (
    <div className={cn('font-sans', className)} {...props}>
      {eyebrow && <p className="pm-eyebrow mb-2.5">{eyebrow}</p>}
      {lead && (
        <p className="mb-3.5 text-body-sm leading-relaxed text-ink">{lead}</p>
      )}
      <div className="rounded-card bg-red-tint px-4 py-4 text-body-sm leading-relaxed text-ink">
        {children}
      </div>
    </div>
  )
}
