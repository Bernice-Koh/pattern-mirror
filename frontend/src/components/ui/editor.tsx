import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface EditorProps extends Omit<
  HTMLAttributes<HTMLDivElement>,
  'title'
> {
  /** Document title value. */
  title?: string
  /** When provided, the title renders as an editable field. */
  onTitleChange?: (value: string) => void
  /** Placeholder shown while the title is empty. */
  titlePlaceholder?: string
  /** Faint meta line, e.g. "Job description · draft". */
  meta?: ReactNode
}

/** The left-pane writing surface: serif title, faint meta, then the document body. */
export function Editor({
  title,
  onTitleChange,
  titlePlaceholder,
  meta,
  className,
  children,
  ...props
}: EditorProps) {
  const titleClasses = 'font-serif text-title font-bold text-ink'

  return (
    <div className={cn('h-full bg-surface px-8 py-7', className)} {...props}>
      {onTitleChange ? (
        <input
          type="text"
          value={title ?? ''}
          onChange={(event) => onTitleChange(event.target.value)}
          placeholder={titlePlaceholder}
          className={cn(
            'w-full max-w-155 bg-transparent outline-none placeholder:text-ink-faint',
            titleClasses,
          )}
        />
      ) : (
        title && <h2 className={titleClasses}>{title}</h2>
      )}
      {meta && (
        <p className="mt-2 font-sans text-meta text-ink-faint">{meta}</p>
      )}
      <div className="mt-5 max-w-155 font-sans text-subheading leading-loose text-ink">
        {children}
      </div>
    </div>
  )
}
