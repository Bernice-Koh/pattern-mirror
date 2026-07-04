import { Link } from '@tanstack/react-router'
import { Chip } from '@/components/ui/chip'
import { SURFACES } from '@/lib/surfaces'
import { useAuth } from '@/lib/use-auth'

/**
 * Temporary surface switcher so the placeholder routes are reachable without
 * editing the URL. Replace once the real navigation IA is designed.
 *
 * Shows only the signed-in role's own surfaces — the route guards already redirect a wrong-role
 * visit, but the nav should not offer a surface the user can't reach (a manager sees no HR Portal,
 * HR sees no manager surfaces). Renders nothing until the user resolves.
 */
export function SurfaceNav() {
  const { user } = useAuth()
  const surfaces = SURFACES.filter((surface) => surface.role === user?.role)

  return (
    <nav className="flex flex-wrap gap-2 border-b border-border bg-surface px-6 py-2">
      {surfaces.map((surface) => (
        <Link key={surface.path} to={surface.path} className="no-underline">
          {({ isActive }) => <Chip active={isActive}>{surface.label}</Chip>}
        </Link>
      ))}
    </nav>
  )
}
