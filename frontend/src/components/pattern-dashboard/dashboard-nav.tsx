import { useAuth } from '@/lib/use-auth'

export type DashboardView = 'patterns' | 'documents' | 'profile' | 'settings'

const NAV_ITEMS: { view: DashboardView; label: string }[] = [
  { view: 'patterns', label: 'Your patterns' },
  { view: 'documents', label: 'My documents' },
  { view: 'profile', label: 'Profile' },
  { view: 'settings', label: 'Settings' },
]

const ROLE_LABELS: Record<'manager' | 'hr', string> = {
  manager: 'Manager',
  hr: 'HR',
}

interface DashboardNavProps {
  active: DashboardView
  onSelect: (view: DashboardView) => void
}

/** The Pattern Dashboard's left rail: the manager's identity and its sub-views (#69).
 *  Distinct from the app-level SurfaceNav — this navigates within the dashboard. */
export function DashboardNav({
  active,
  onSelect,
}: Readonly<DashboardNavProps>) {
  const { user } = useAuth()

  return (
    <aside className="border-r border-border bg-surface px-5 py-7">
      <div className="flex size-16 items-center justify-center rounded-full bg-chip-track font-sans text-heading font-semibold text-ink">
        {user?.initials ?? ''}
      </div>
      <div className="mt-4">
        <div className="font-sans text-subheading font-bold text-ink">
          {user?.legalName ?? ''}
        </div>
        <div className="mt-0.5 font-sans text-body-sm text-ink-muted">
          {user ? ROLE_LABELS[user.role] : ''}
        </div>
      </div>
      <nav className="mt-7 flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = item.view === active
          return (
            <button
              key={item.view}
              type="button"
              onClick={() => onSelect(item.view)}
              className={`rounded-md px-3 py-2.5 text-left font-sans text-body-sm transition-colors ${
                isActive
                  ? 'bg-red-tint font-semibold text-red-primary'
                  : 'text-ink-muted hover:bg-canvas'
              }`}
            >
              {item.label}
            </button>
          )
        })}
      </nav>
    </aside>
  )
}
