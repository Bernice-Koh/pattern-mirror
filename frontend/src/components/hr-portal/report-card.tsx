import type { ReactNode } from 'react'

/** Neutral placeholder shown in place of a chart when a dimension has no data yet. */
export function ReportEmptyState({ message }: Readonly<{ message: string }>) {
  return (
    <div className="flex h-42 items-center justify-center rounded-md border border-dashed border-border px-6">
      <span className="max-w-xs text-center font-sans text-body-sm text-ink-faint">
        {message}
      </span>
    </div>
  )
}

interface ReportCardProps {
  title: string
  caption?: string
  children: ReactNode
}

/** A titled surface card for one report dimension, matching the HR Portal mockup's CardShell. */
export function ReportCard({
  title,
  caption,
  children,
}: Readonly<ReportCardProps>) {
  return (
    <div className="rounded-card bg-surface p-6 shadow-ring-card">
      <h3 className="font-sans text-subheading font-semibold text-ink">
        {title}
      </h3>
      {caption && (
        <p className="mt-0.5 mb-4 font-sans text-label text-ink-faint">
          {caption}
        </p>
      )}
      <div className={caption ? '' : 'mt-4'}>{children}</div>
    </div>
  )
}
