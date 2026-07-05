import { useState } from 'react'
import { cn } from '@/lib/cn'
import { useAuth } from '@/lib/use-auth'

export type DashboardView = 'patterns' | 'documents'

const NAV_ITEMS: { view: DashboardView; label: string }[] = [
  { view: 'patterns', label: 'Your patterns' },
  { view: 'documents', label: 'My documents' },
]

const ROLE_LABELS: Record<'manager' | 'hr', string> = {
  manager: 'Manager',
  hr: 'HR',
}

// Persisted so the choice survives switching sub-views and leaving/returning to the dashboard
// within the session; best-effort, since localStorage can be unavailable (private mode).
const STORAGE_KEY = 'pm:dashboard-rail-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

function writeCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0')
  } catch {
    // ignore
  }
}

/** The three-line menu (hamburger) that toggles the rail, GitHub's sidebar-button style. */
function MenuIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

interface DashboardNavProps {
  active: DashboardView
  onSelect: (view: DashboardView) => void
}

/** The Pattern Dashboard's left rail: the manager's identity and its sub-views (#69). Distinct from
 *  the app-level SurfaceNav — this navigates within the dashboard. Collapsible to reclaim horizontal
 *  space for the content; the collapsed state persists across the dashboard's views. */
export function DashboardNav({
  active,
  onSelect,
}: Readonly<DashboardNavProps>) {
  const { user } = useAuth()
  const [collapsed, setCollapsed] = useState(readCollapsed)

  function toggle() {
    setCollapsed((current) => {
      const next = !current
      writeCollapsed(next)
      return next
    })
  }

  return (
    <aside
      className={cn(
        'shrink-0 border-r border-border bg-surface py-7 transition-[width] duration-200',
        collapsed ? 'w-14 px-2' : 'w-60 px-5',
      )}
    >
      <div className={cn('flex', collapsed ? 'justify-center' : 'justify-end')}>
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
          className="rounded-md p-1.5 text-ink-muted transition-colors hover:bg-canvas hover:text-ink"
        >
          <MenuIcon />
        </button>
      </div>

      {!collapsed && (
        <>
          <div className="mt-2 flex size-16 items-center justify-center rounded-full bg-chip-track font-sans text-heading font-semibold text-ink">
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
        </>
      )}
    </aside>
  )
}
