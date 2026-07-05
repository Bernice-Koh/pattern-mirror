import type { ErrorComponentProps } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

/** Catches a render/load error in any route so a single bad record degrades to a recoverable
 *  message instead of white-screening the whole app. */
export function RouteError({ reset }: ErrorComponentProps) {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 px-6 text-center">
      <p className="font-sans text-subheading font-semibold text-ink">
        Something went wrong loading this view.
      </p>
      <p className="max-w-md font-sans text-body-sm text-ink-muted">
        Your work is saved. Try again, or reload the page.
      </p>
      <Button variant="secondary" size="md" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}
