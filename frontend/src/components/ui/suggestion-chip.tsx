import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface SuggestionChipProps {
  /** Highlighted as the pick that Apply will use. */
  readonly selected?: boolean
  readonly onClick?: () => void
  readonly children: ReactNode
}

/** Alternative-phrasing pill shared by the flag card and popover. Metrics mirror the
 *  design-system SuggestionChip; selected (not click) is what Apply reads. */
export function SuggestionChip({
  selected = false,
  onClick,
  children,
}: SuggestionChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={cn(
        'rounded-pill px-3 py-[7px] text-[12.5px] leading-tight font-medium transition-colors',
        selected
          ? 'bg-red-tint text-red-primary'
          : 'bg-canvas text-ink hover:bg-red-tint hover:text-red-primary',
      )}
    >
      {children}
    </button>
  )
}
