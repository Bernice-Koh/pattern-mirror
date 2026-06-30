import { useState, type CSSProperties } from 'react'
import type { DecisionPattern } from '@/lib/patterns-contract'
import { decisionStatement } from '@/lib/decision-statement'
import { PatternDrillDown } from '@/components/pattern-dashboard/pattern-drill-down'

interface BehaviouralPatternCardProps {
  pattern: DecisionPattern
}

/** One significant decision pattern (design spec §2 View 3 Layer 2, §13): a flat factual statement
 *  of how often the manager revised a category's flagged language, its adoption rate, p-value, and a
 *  toggle into the source documents. Pure presentation over the gated facts from #66 — no scoring. */
export function BehaviouralPatternCard({
  pattern,
}: Readonly<BehaviouralPatternCardProps>) {
  const [expanded, setExpanded] = useState(false)
  const { eyebrow, sentence, rate, rateLabel, pValueLabel, notesCount } =
    decisionStatement(pattern)

  return (
    <div className="flex flex-col gap-3.5 rounded-card bg-surface p-5 font-sans shadow-ring-card">
      <span className="text-meta text-ink-faint">{eyebrow}</span>
      <p className="text-body leading-relaxed text-ink">{sentence}</p>

      <div className="flex items-center gap-3">
        <span className="block h-2 w-35 overflow-hidden rounded bg-chip-track">
          <span
            className="block h-full w-(--bar-fill) rounded bg-purple-pattern"
            style={
              {
                '--bar-fill': `${Math.min(100, rate * 100)}%`,
              } as CSSProperties
            }
          />
        </span>
        <span className="text-body-sm text-ink-muted">{rateLabel}</span>
      </div>

      <div className="flex items-center justify-between">
        <span className="rounded-pill bg-chip-track px-2.5 py-1 text-meta text-ink-muted">
          p = {pValueLabel}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((open) => !open)}
          aria-expanded={expanded}
          className="font-sans text-body-sm font-semibold text-red-primary"
        >
          {expanded ? 'Hide notes' : `View ${notesCount} notes →`}
        </button>
      </div>

      {expanded && <PatternDrillDown documentIds={pattern.document_ids} />}
    </div>
  )
}
