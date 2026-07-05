import { useState } from 'react'
import {
  DashboardNav,
  type DashboardView,
} from '@/components/pattern-dashboard/dashboard-nav'
import { MyDocuments } from '@/components/pattern-dashboard/my-documents'
import { YourPatterns } from '@/components/pattern-dashboard/your-patterns'

/** View 3 — the Pattern Dashboard shell: a left rail over the manager's sub-views.
 *  My Documents (#69) is the navigation root; the pattern surfaces land in #67/#68. */
export function PatternDashboard() {
  const [view, setView] = useState<DashboardView>('documents')

  return (
    <div className="flex min-h-[calc(100vh-7rem)] bg-canvas">
      <DashboardNav active={view} onSelect={setView} />
      <main className="flex-1 overflow-auto px-10 py-9">
        {view === 'documents' && <MyDocuments />}
        {view === 'patterns' && <YourPatterns />}
      </main>
    </div>
  )
}
