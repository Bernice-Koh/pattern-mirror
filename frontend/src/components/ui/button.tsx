import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

const button = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-button border border-transparent font-sans font-semibold leading-none transition-colors disabled:cursor-not-allowed disabled:opacity-45',
  {
    variants: {
      variant: {
        primary: 'bg-red-primary text-white hover:bg-red-press',
        secondary:
          'border-border bg-surface text-ink hover:border-ink-faint hover:bg-surface-alt',
        ghost: 'bg-transparent text-red-primary hover:bg-red-tint',
      },
      size: {
        sm: 'px-3 py-1.5 text-meta',
        md: 'px-4 py-2 text-label',
        lg: 'px-5 py-3 text-body-sm',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export interface ButtonProps
  extends
    ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

/** Primary action control — red filled, secondary outline, or inline ghost. */
export function Button({
  variant,
  size,
  className,
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  // A filled (red) button's white label reads optically high against the saturated fill, so the
  // label is nudged down a hair. Outlined/ghost buttons centre correctly and are left untouched.
  const filled = variant === undefined || variant === 'primary'
  return (
    <button
      type={type}
      className={cn(button({ variant, size }), className)}
      {...props}
    >
      {filled ? (
        <span className="inline-flex translate-y-px items-center gap-2">
          {children}
        </span>
      ) : (
        children
      )}
    </button>
  )
}
