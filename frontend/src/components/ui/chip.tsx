import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  /** Selected / contextual red-tint look. @default false */
  active?: boolean
}

/** Context / criteria pill — fully rounded, inert by default. */
export function Chip({ active = false, className, ...props }: ChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-pill px-3.5 py-2 font-sans text-label leading-none font-medium whitespace-nowrap',
        active
          ? 'bg-red-tint text-red-primary'
          : 'bg-chip-track text-ink-muted',
        className,
      )}
      {...props}
    />
  )
}
