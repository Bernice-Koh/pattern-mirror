import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface FlagPopoverProps extends HTMLAttributes<HTMLDivElement> {
  category: string
  /** "dictionary" or "AI pass" — drives the dot colour. */
  source: string
  explanation?: string
  citation?: string
  suggestions?: string[]
  onApply?: (suggestion: string) => void
  onKeep?: () => void
  onDismiss?: () => void
}

/** Floating evidence card anchored to a flagged span: category, explanation,
 *  citation, and optional alternatives. Actions render only when wired. */
export function FlagPopover({
  category,
  source,
  explanation = '',
  citation = '',
  suggestions = [],
  onApply,
  onKeep,
  onDismiss,
  className,
  ...props
}: FlagPopoverProps) {
  const isAi = source.toLowerCase().includes('ai')
  const hasActions = Boolean(onApply || onKeep || onDismiss)

  return (
    <div
      role="dialog"
      className={cn(
        'flex w-66 flex-col gap-2.5 rounded-popover bg-surface p-3.5 font-sans shadow-popover',
        className,
      )}
      {...props}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            'size-2 shrink-0 rounded-full',
            isAi ? 'bg-amber-contextual' : 'bg-red-primary',
          )}
        />
        <span className="text-micro text-ink-faint">
          {category} · {source}
        </span>
      </div>

      {explanation && (
        <p className="text-label leading-snug text-ink">{explanation}</p>
      )}
      {citation && <p className="text-micro text-ink-faint">{citation}</p>}

      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onApply?.(suggestion)}
              className="rounded-pill bg-canvas px-3 py-1.5 text-micro font-medium text-ink transition-colors hover:bg-red-tint hover:text-red-primary"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {hasActions && (
        <div className="mt-0.5 flex items-center gap-3">
          {onApply && suggestions.length > 0 && (
            <button
              type="button"
              onClick={() => onApply(suggestions[0])}
              className="rounded-button bg-red-primary px-3.5 py-1.5 text-micro font-semibold text-white transition-colors hover:bg-red-press"
            >
              Apply
            </button>
          )}
          {onKeep && (
            <button
              type="button"
              onClick={onKeep}
              className="text-micro text-ink-faint"
            >
              or keep
            </button>
          )}
          {onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss flag"
              className="ml-auto text-base leading-none text-ink-faint"
            >
              ×
            </button>
          )}
        </div>
      )}
    </div>
  )
}
