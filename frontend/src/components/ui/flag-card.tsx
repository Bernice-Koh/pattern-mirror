import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface FlagCardProps extends HTMLAttributes<HTMLDivElement> {
  category?: string
  /** "dictionary" or "AI pass" — drives the dot colour. */
  source?: string
  /** Original flagged phrase (rendered struck). */
  original?: string
  /** Suggested replacement shown after the arrow. */
  replacement?: string
  explanation?: string
  citation?: string
  suggestions?: string[]
  /** Greyed, struck, Undo-only. @default false */
  dismissed?: boolean
  onApply?: (suggestion: string) => void
  onDismiss?: () => void
  onUndo?: () => void
}

/** A flag in the right-hand analysis panel — evidence + alternatives + Apply/×; dismissed shows Undo. */
export function FlagCard({
  category = 'Gender-coded',
  source = 'dictionary',
  original,
  replacement,
  explanation = '',
  citation = '',
  suggestions = [],
  dismissed = false,
  onApply,
  onDismiss,
  onUndo,
  className,
  ...props
}: FlagCardProps) {
  const isAi = source.toLowerCase().includes('ai')
  const dotColor = dismissed
    ? 'bg-ink-faint'
    : isAi
      ? 'bg-amber-contextual'
      : 'bg-red-primary'

  return (
    <div
      className={cn(
        'flex flex-col gap-2 rounded-card bg-surface p-4 font-sans shadow-ring-card',
        dismissed && 'opacity-60',
        className,
      )}
      {...props}
    >
      <div className="flex items-center gap-2">
        <span className={cn('size-2 shrink-0 rounded-full', dotColor)} />
        <span className="text-micro text-ink-faint">
          {category} · {dismissed ? 'dismissed' : source}
        </span>
      </div>

      {(original || replacement) && (
        <div className="text-label text-ink-muted">
          <span className="line-through">{original}</span>
          {replacement && <span> → {replacement}</span>}
        </div>
      )}

      {explanation && !dismissed && (
        <p className="text-micro leading-normal text-ink-muted">
          {explanation}
        </p>
      )}

      {suggestions.length > 0 && !dismissed && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onApply?.(suggestion)}
              className="rounded-pill bg-chip-track px-2.5 py-1 text-micro font-medium text-ink-muted transition-colors hover:bg-red-tint hover:text-red-primary"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {citation && !dismissed && (
        <p className="text-micro text-ink-faint">{citation}</p>
      )}

      <div className="mt-0.5 flex items-center gap-2.5">
        {dismissed ? (
          <button
            type="button"
            onClick={onUndo}
            className="text-micro font-semibold text-red-primary"
          >
            Undo
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => {
                if (suggestions.length > 0) onApply?.(suggestions[0])
              }}
              className="rounded-button bg-red-primary px-3.5 py-1.5 text-micro font-semibold text-white transition-colors hover:bg-red-press"
            >
              Apply
            </button>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss flag"
              className="ml-auto text-base leading-none text-ink-faint"
            >
              ×
            </button>
          </>
        )}
      </div>
    </div>
  )
}
