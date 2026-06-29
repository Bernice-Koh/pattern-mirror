import type { SaveState } from '@/components/jd-studio/use-document-session'

/** Cloud-with-check mark — the rest state once a draft is safely autosaved. */
function CloudCheck() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="13"
      height="13"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M17.5 19a4.5 4.5 0 0 0 .5-9 6 6 0 0 0-11.5-1.5A4 4 0 0 0 6.5 19Z" />
      <path d="m9 14 2 2 4-4" />
    </svg>
  )
}

/** The draft's transient save state, shown in the editor meta line. Idle renders nothing so
 *  the line stays quiet until the first autosave. */
export function AutosaveStatus({ state }: Readonly<{ state: SaveState }>) {
  if (state === 'idle') return null

  if (state === 'saving') {
    return (
      <span className="inline-flex items-center gap-1.5 text-ink-faint">
        <span className="size-3 animate-spin rounded-full border-[1.6px] border-border border-t-ink-faint" />{' '}
        Saving…
      </span>
    )
  }

  if (state === 'error') {
    return <span className="text-red-primary">Couldn’t save</span>
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-ink-faint">
      <CloudCheck />
      Saved
    </span>
  )
}
