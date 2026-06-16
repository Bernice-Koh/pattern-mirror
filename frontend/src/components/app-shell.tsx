import { Outlet, useRouterState } from '@tanstack/react-router'
import { TopBar } from '@/components/ui/top-bar'
import { SurfaceNav } from '@/components/surface-nav'
import { SURFACES } from '@/lib/surfaces'
import { currentUser } from '@/lib/current-user'

/** Persistent app frame: top bar (surface driven by the active route) and the
 *  temporary surface nav above the routed outlet. */
export function AppShell() {
  const surface = useRouterState({
    select: (state) =>
      SURFACES.find((s) => s.path === state.location.pathname)?.label ??
      'JD Studio',
  })

  return (
    <div className="min-h-screen bg-canvas">
      <TopBar surface={surface} initials={currentUser.initials} />
      <SurfaceNav />
      <Outlet />
    </div>
  )
}
