import type { ReactNode } from 'react'

export interface SurfacePlaceholderProps {
  /** Surface name, rendered as the page title. */
  surface: string
  /** One-line description of what the finished surface will do. */
  description: string
  children?: ReactNode
}

/** Shared shell for the not-yet-built surface routes: eyebrow, title, blurb. */
export function SurfacePlaceholder({
  surface,
  description,
  children,
}: SurfacePlaceholderProps) {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <p className="pm-eyebrow">Pattern Mirror</p>
      <h1 className="mt-2">{surface}</h1>
      <p className="mt-3 max-w-prose text-body text-ink-muted">{description}</p>
      <p className="mt-6 text-meta text-ink-faint">
        Placeholder surface — the full screen is built in a later feature issue.
      </p>
      {children}
    </main>
  )
}
