import { useState } from 'react'
import {
  DashboardNav,
  type DashboardView,
} from '@/components/pattern-dashboard/dashboard-nav'
import { MyDocuments } from '@/components/pattern-dashboard/my-documents'
import { YourPatterns } from '@/components/pattern-dashboard/your-patterns'

// Copy for the static views; Your patterns (#67) and My documents (#69) own their own components.
const PLACEHOLDERS: Record<
  'profile' | 'settings',
  { title: string; body: string }
> = {
  profile: {
    title: 'Profile',
    body: 'Your role, reports, and team — used only to scope your own patterns.',
  },
  settings: {
    title: 'Settings',
    body: 'Notification cadence and analysis preferences.',
  },
}

function PlaceholderView({ view }: Readonly<{ view: 'profile' | 'settings' }>) {
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
        {view === 'documents' && <MyDocuments />}
        {view === 'patterns' && <YourPatterns />}
        {(view === 'profile' || view === 'settings') && (
          <PlaceholderView view={view} />
        )}
      </main>
    </div>
  )
}
