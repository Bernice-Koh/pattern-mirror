import { Link } from '@tanstack/react-router'
import { Chip } from '@/components/ui/chip'
import { SURFACES } from '@/lib/surfaces'

/**
 * Temporary surface switcher so the placeholder routes are reachable without
 * editing the URL. Replace once the real navigation IA is designed.
 */
export function SurfaceNav() {
  return (
    <nav className="flex flex-wrap gap-2 border-b border-border bg-surface px-6 py-2">
      {SURFACES.map((surface) => (
        <Link key={surface.path} to={surface.path} className="no-underline">
          {({ isActive }) => <Chip active={isActive}>{surface.label}</Chip>}
        </Link>
      ))}
    </nav>
  )
}
