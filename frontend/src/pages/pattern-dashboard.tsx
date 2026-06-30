import { useState } from 'react'
import {
  DashboardNav,
  type DashboardView,
} from '@/components/pattern-dashboard/dashboard-nav'
import { MyDocuments } from '@/components/pattern-dashboard/my-documents'

// Copy for the views #69 doesn't own; Your patterns is filled by #67/#68, the rest are static.
const PLACEHOLDERS: Record<
  Exclude<DashboardView, 'documents'>,
  { title: string; body: string }
> = {
  patterns: {
    title: 'Your patterns',
    body: 'How your writing and decisions have changed over time. Only patterns that pass Fisher’s exact significance testing appear here.',
  },
  profile: {
    title: 'Profile',
    body: 'Your role, reports, and team — used only to scope your own patterns.',
  },
  settings: {
    title: 'Settings',
    body: 'Notification cadence and analysis preferences.',
  },
}

function PlaceholderView({
  view,
}: Readonly<{ view: Exclude<DashboardView, 'documents'> }>) {
  const { title, body } = PLACEHOLDERS[view]
  return (
    <div className="max-w-170">
      <h1 className="font-serif text-display font-bold text-ink">{title}</h1>
      <p className="mt-3 font-sans text-body leading-relaxed text-ink-muted">
        {body} This is your own data — visible only to you.
      </p>
    </div>
  )
}

/** View 3 — the Pattern Dashboard shell: a left rail over the manager's sub-views.
 *  My Documents (#69) is the navigation root; the pattern surfaces land in #67/#68. */
export function PatternDashboard() {
  const [view, setView] = useState<DashboardView>('documents')

  return (
    <div className="grid min-h-[calc(100vh-7rem)] grid-cols-[240px_1fr] bg-canvas">
      <DashboardNav active={view} onSelect={setView} />
      <main className="overflow-auto px-10 py-9">
        {view === 'documents' ? (
          <MyDocuments />
        ) : (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  )
}
