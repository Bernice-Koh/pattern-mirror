import { type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { WritingPattern } from '@/lib/patterns-contract'
import { getPatterns } from '@/lib/patterns-client'
import { PatternCard } from '@/components/pattern-dashboard/pattern-card'
import { WritingVolumeTrends } from '@/components/pattern-dashboard/writing-volume-trends'
import { BehaviouralReflection } from '@/components/pattern-dashboard/behavioural-reflection'

const ACROSS_TIME_TITLE = 'Across your history'

function PatternGrid({
  scope,
  patterns,
}: Readonly<{ scope: string; patterns: WritingPattern[] }>) {
  return (
    <section className="mb-6">
      <p className="mb-2.5 font-sans text-eyebrow font-semibold tracking-wide text-ink-faint uppercase">
        {scope}
      </p>
      <div className="grid grid-cols-2 gap-5">
        {patterns.map((pattern) => (
          <PatternCard
            key={`${pattern.mode}:${pattern.role_title}:${pattern.term}`}
            pattern={pattern}
          />
        ))}
      </div>
    </section>
  )
}

/** Group per-role patterns under their role title; across-time under one history heading. A
 *  per-role pattern already shown across the whole history is dropped as a duplicate — when one
 *  role dominates a manager's writing the two modes coincide, so a role section surfaces only the
 *  patterns unique to that role (and disappears entirely when it has none). */
function groupByScope(
  patterns: WritingPattern[],
): { title: string; patterns: WritingPattern[] }[] {
  const acrossTime = patterns.filter(
    (pattern) => pattern.mode === 'across_time',
  )
  const acrossKeys = new Set(
    acrossTime.map((pattern) => `${pattern.category}:${pattern.term}`),
  )
  const byRole = new Map<string, WritingPattern[]>()
  for (const pattern of patterns) {
    if (pattern.mode !== 'per_role') continue
    if (acrossKeys.has(`${pattern.category}:${pattern.term}`)) continue
    const role = pattern.role_title ?? 'A role'
    byRole.set(role, [...(byRole.get(role) ?? []), pattern])
  }

  const groups: { title: string; patterns: WritingPattern[] }[] = []
  if (acrossTime.length > 0) {
    groups.push({ title: ACROSS_TIME_TITLE, patterns: acrossTime })
  }
  for (const [role, rolePatterns] of byRole) {
    groups.push({ title: role, patterns: rolePatterns })
  }
  return groups
}

/** View 3 — the manager's pattern dashboard: significant writing patterns as cards with drill-down
 *  (Layer 1, #67) and the behavioural-reflection layer below (Layer 2, #68). Both are live over the
 *  gated aggregator output (#66); the overview sections above stay static scaffold for now. */
export function YourPatterns() {
  const { data, isLoading } = useQuery({
    queryKey: ['patterns'],
    queryFn: getPatterns,
  })

  const writingPatterns = data?.writing_patterns ?? []
  const groups = groupByScope(writingPatterns)

  let recurring: ReactNode
  if (isLoading) {
    recurring = <p className="font-sans text-label text-ink-faint">Loading…</p>
  } else if (writingPatterns.length === 0) {
    recurring = (
      <p className="rounded-card bg-surface p-5 font-sans text-body-sm text-ink-muted shadow-ring-card">
        No clear patterns have emerged yet. Patterns appear here only once they
        are unlikely to be a coincidence.
      </p>
    )
  } else {
    recurring = groups.map((group) => (
      <PatternGrid
        key={group.title}
        scope={group.title}
        patterns={group.patterns}
      />
    ))
  }

  return (
    <div className="max-w-270">
      <h1 className="font-serif text-display font-bold text-ink">
        Your patterns
      </h1>
      <p className="mt-2.5 mb-7 max-w-165 font-sans text-body leading-relaxed text-ink-muted">
        How your writing and decisions have changed over time. Only patterns
        unlikely to be a coincidence appear here.
      </p>

      {!isLoading && (
        <WritingVolumeTrends
          flagVolume={data?.flag_volume_trend ?? []}
          improvements={data?.category_improvements ?? []}
        />
      )}

      <h2 className="mb-3.5 font-sans text-body-sm font-semibold text-ink-muted">
        Still recurring
      </h2>
      <div className="mb-7">{recurring}</div>

      {!isLoading && (
        <BehaviouralReflection
          patterns={data?.decision_patterns ?? []}
          trend={data?.adoption_trend ?? []}
        />
      )}

      <p className="mt-2 border-t border-border pt-4 font-sans text-meta text-ink-faint">
        Only patterns unlikely to be a coincidence appear here. This is your own
        data — visible only to you.
      </p>
    </div>
  )
}
