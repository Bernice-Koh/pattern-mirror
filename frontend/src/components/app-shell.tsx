import { Outlet, useNavigate, useRouterState } from '@tanstack/react-router'
import { TopBar } from '@/components/ui/top-bar'
import { SurfaceNav } from '@/components/surface-nav'
import { SURFACES } from '@/lib/surfaces'
import { useAuth } from '@/lib/use-auth'

/** Persistent app frame: top bar (surface driven by the active route) and the
 *  temporary surface nav above the routed outlet. */
export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const surface = useRouterState({
    select: (state) => {
      const { pathname } = state.location
      // Longest-prefix match so sub-pages (e.g. /hr-portal/dictionary-review) keep their
      // surface's label rather than falling through to the default.
      const match = [...SURFACES]
        .filter((s) => pathname === s.path || pathname.startsWith(`${s.path}/`))
        .sort((a, b) => b.path.length - a.path.length)[0]
      return match?.label ?? 'JD Studio'
    },
  })

  async function handleLogout() {
    logout()
    await navigate({ to: '/login' })
  }

  return (
    <div className="min-h-screen bg-canvas">
      <TopBar
        surface={surface}
        initials={user?.initials ?? ''}
        onLogout={handleLogout}
      />
      <SurfaceNav />
      <Outlet />
    </div>
  )
}
