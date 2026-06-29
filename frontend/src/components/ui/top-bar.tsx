import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import ubsLogo from '@/assets/UBS_Logo.svg'
import { Button } from '@/components/ui/button'
import { Chip } from '@/components/ui/chip'

export interface TopBarProps extends HTMLAttributes<HTMLElement> {
  /** Surface name shown after "Pattern Mirror ·". @default "JD Studio" */
  surface?: string
  /** Context chips (subject, role/tier, scope). */
  chips?: string[]
  /** Avatar initials. @default "DK" */
  initials?: string
  /** Primary action label (renders a red button). Omit for none. */
  action?: string | null
  onAction?: () => void
  /** When set, the avatar becomes a log-out control. */
  onLogout?: () => void
}

/** Persistent app top bar: wordmark + breadcrumb left, context chips + avatar (+ optional action) right. */
export function TopBar({
  surface = 'JD Studio',
  chips = [],
  initials = 'DK',
  action = null,
  onAction,
  onLogout,
  className,
  ...props
}: TopBarProps) {
  const avatarClass =
    'flex size-9 items-center justify-center rounded-full bg-chip-track font-sans text-label font-semibold text-ink-muted'
  return (
    <header
      className={cn(
        'flex h-16 items-center justify-between border-b border-border bg-surface px-6',
        className,
      )}
      {...props}
    >
      <div className="flex items-center gap-3.5">
        <img src={ubsLogo} alt="UBS" className="h-6 w-auto" />
        <span className="h-5 w-px bg-border" aria-hidden="true" />
        <span className="font-sans text-label text-ink-muted">
          Pattern Mirror · {surface}
        </span>
      </div>
      <div className="flex items-center gap-3">
        {chips.map((chip, index) => (
          <Chip key={index}>{chip}</Chip>
        ))}
        {action && (
          <Button variant="primary" size="md" onClick={onAction}>
            {action}
          </Button>
        )}
        {onLogout ? (
          <button
            type="button"
            onClick={onLogout}
            title="Log out"
            className={cn(avatarClass, 'transition-colors hover:bg-border')}
          >
            {initials}
          </button>
        ) : (
          <span className={avatarClass}>{initials}</span>
        )}
      </div>
    </header>
  )
}
