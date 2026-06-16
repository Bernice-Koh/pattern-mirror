import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

const badge = cva(
  'inline-flex h-5 min-w-5 items-center justify-center rounded-pill px-2 font-sans text-meta font-semibold leading-none',
  {
    variants: {
      tone: {
        red: 'bg-red-primary text-white',
        neutral: 'bg-chip-track text-ink-muted',
        green: 'bg-green-positive text-white',
      },
    },
    defaultVariants: { tone: 'red' },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badge> {}

/** Small count / status badge — red flag-count, neutral inert pill, green positive. */
export function Badge({ tone, className, ...props }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)} {...props} />
}
