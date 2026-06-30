/** Layout scaffold for the still-static overview sections of the Pattern Dashboard (design spec
 *  §2 View 3): headline stat cards and the AI summary. These render as pending placeholders — no
 *  data is fabricated. The writing-volume trends below them are live (#99); the behavioural
 *  reflection layer is live in its own section (#68). */

const STAT_LABELS = [
  'Bias flags vs your first sessions',
  'Recurring patterns',
  'Adoption rate',
]

function StatCardStub({ label }: Readonly<{ label: string }>) {
  return (
    <div className="flex flex-col gap-2.5 rounded-card bg-canvas px-5 py-5 font-sans">
      <span className="text-body-sm text-ink-muted">{label}</span>
      <span className="text-metric font-semibold text-ink-faint">—</span>
      <span className="text-meta text-ink-faint">
        Available as your history grows
      </span>
    </div>
  )
}

/** The non-live overview sections, rendered above the live trends and writing-pattern cards. */
export function PatternOverviewStub() {
  return (
    <>
      <div className="mb-6 grid grid-cols-3 gap-4.5">
        {STAT_LABELS.map((label) => (
          <StatCardStub key={label} label={label} />
        ))}
      </div>

      <div className="mb-6 rounded-card bg-surface p-6 shadow-ring-card">
        <div className="mb-3 font-sans text-eyebrow font-semibold tracking-wide text-ink-faint uppercase">
          AI summary
        </div>
        <p className="font-sans text-body leading-relaxed text-ink-muted">
          A plain-language summary of your patterns will appear here as your
          history grows.
        </p>
      </div>
    </>
  )
}
