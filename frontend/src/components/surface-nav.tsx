import { Link } from '@tanstack/react-router'
import { SURFACES } from '@/lib/surfaces'
import { useAuth } from '@/lib/use-auth'

/**
 * The app-level surface navigation: underline tabs matching the in-page tab style (My Documents),
 * sized to the layout's fixed 48px nav band so the surfaces' `100vh-7rem` budget stays exact.
 *
 * Shows only the signed-in role's own surfaces — the route guards already redirect a wrong-role
 * visit, but the nav should not offer a surface the user can't reach (a manager sees no HR Portal,
 * HR sees no manager surfaces). Renders nothing until the user resolves.
 */
export function SurfaceNav() {
  const { user } = useAuth()
  const surfaces = SURFACES.filter((surface) => surface.role === user?.role)

  return (
    <nav className="flex h-12 items-stretch gap-1 border-b border-border bg-surface px-6">
      {surfaces.map((surface) => (
        <Link key={surface.path} to={surface.path} className="no-underline">
          {({ isActive }) => (
            <span
              className={`-mb-px flex h-full items-center border-b-2 px-3.5 font-sans text-body-sm transition-colors ${
                isActive
                  ? 'border-red-primary font-semibold text-ink'
                  : 'border-transparent text-ink-muted hover:text-ink'
              }`}
            >
              {surface.label}
            </span>
          )}
        </Link>
      ))}
    </nav>
  )
}
