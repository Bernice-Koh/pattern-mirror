import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface CoverageItem {
  label: string
  addressed: boolean
  /** Overrides the default "addressed" / "not addressed" status text. */
  statusLabel?: string
}

export interface CoverageListProps extends HTMLAttributes<HTMLDivElement> {
  /** Card heading. @default "Coverage" */
  title?: string
  /** Right-aligned pill, e.g. "3 of 4 not addressed". */
  summary?: string
  items: CoverageItem[]
}

/** Criteria coverage — each row is a reference criterion the draft did (✓) or didn't (✕) address.
 *  Corpus-agnostic: shared by Feedback Checkpoint and Promotion Writeup over the drift-findings
 *  contract, the surface supplying the title and status wording. */
export function CoverageList({
  title = 'Coverage',
  summary,
  items,
  className,
  ...props
}: CoverageListProps) {
  return (
    <div
      className={cn(
        'rounded-card bg-surface p-5 font-sans shadow-ring-card',
        className,
      )}
      {...props}
    >
      <div className="mb-3.5 flex items-center justify-between">
        <h3 className="font-sans text-subheading font-semibold text-ink">
          {title}
        </h3>
        {summary && (
          <span className="rounded-pill bg-chip-track px-2.5 py-1 text-meta text-ink-muted">
            {summary}
          </span>
        )}
      </div>
      <div className="flex flex-col">
        {items.map((item, index) => (
          <div
            key={item.label}
            className={cn(
              'flex items-center gap-3 py-2.5',
              index > 0 && 'border-t border-border',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'w-4 text-center text-label font-bold',
                item.addressed ? 'text-green-positive' : 'text-ink-faint',
              )}
            >
              {item.addressed ? '✓' : '✕'}
            </span>
            <span className="flex-1 text-label text-ink">{item.label}</span>
            <span
              className={cn(
                'text-meta',
                item.addressed ? 'text-green-positive' : 'text-ink-faint',
              )}
            >
              {item.statusLabel ?? (item.addressed ? 'addressed' : 'not addressed')}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
