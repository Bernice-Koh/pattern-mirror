import { forwardRef, type InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Text input styled to the kit: used by the login forms. */
export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        'w-full rounded-button border border-border bg-surface px-3 py-2 font-sans text-body-sm text-ink',
        'placeholder:text-ink-faint focus:border-ink-faint focus:outline-none',
        className,
      )}
      {...props}
    />
  )
})
