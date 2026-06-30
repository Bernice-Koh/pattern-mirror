/** Layout scaffold for the overview sections of the Pattern Dashboard (design spec §2 View 3):
 *  headline stats, AI summary, the bias-flags trend, and per-category improvement. These render
 *  as pending placeholders — no data is fabricated. The behavioural reflection layer is live in its
 *  own section (#68); these writing-volume trends fill in with #99. */

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

function PanelStub({
  title,
  caption,
  pending,
}: Readonly<{ title: string; caption: string; pending: string }>) {
  return (
    <div className="rounded-card bg-surface p-6 shadow-ring-card">
      <h3 className="font-sans text-subheading font-semibold text-ink">
        {title}
      </h3>
      <p className="mt-0.5 mb-4 font-sans text-label text-ink-faint">
        {caption}
      </p>
      <div className="flex h-42 items-center justify-center rounded-md border border-dashed border-border">
        <span className="font-sans text-body-sm text-ink-faint">{pending}</span>
      </div>
    </div>
  )
}

/** The non-live overview sections, rendered above the live writing-pattern cards. */
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

      <div className="mb-7 grid grid-cols-[1.2fr_1fr] gap-5.5">
        <PanelStub
          title="Bias flags over time"
          caption="Average flags per document, over time"
          pending="Not enough history yet"
        />
        <PanelStub
          title="Where you've improved"
          caption="Reduction in flagged language, by category"
          pending="No category trends yet"
        />
      </div>
    </>
  )
}
