import { useMemo, useState } from 'react'
import {
  CATEGORY_LABELS,
  formatCitation,
  sourceLabel,
  type BiasCategory,
  type CitedFlag,
} from '@/lib/analyze-contract'
import { Badge } from '@/components/ui/badge'
import { CategorySummary } from '@/components/ui/category-summary'
import { Editor } from '@/components/ui/editor'
import { FlagCard } from '@/components/ui/flag-card'
import { Legend } from '@/components/ui/legend'
import { JdEditor } from '@/components/jd-studio/jd-editor'

export function JdStudio() {
  const [title, setTitle] = useState('')
  const [flags, setFlags] = useState<CitedFlag[]>([])

  const categoryItems = useMemo(() => {
    const counts = new Map<BiasCategory, number>()
    for (const flag of flags) {
      counts.set(flag.category, (counts.get(flag.category) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([category, count]) => ({ label: CATEGORY_LABELS[category], count }))
      .sort((a, b) => b.count - a.count)
  }, [flags])

  return (
    <main className="flex h-[calc(100vh-7rem)] flex-col bg-surface">
      <div className="grid min-h-0 flex-1 grid-cols-[58%_42%]">
        <div className="overflow-auto border-r border-border">
          <Editor
            title={title}
            onTitleChange={setTitle}
            titlePlaceholder="Untitled job description"
            meta="Job description · draft"
          >
            <JdEditor docType="jd" initialContent="" onFlagsChange={setFlags} />
          </Editor>
        </div>

        <aside className="overflow-auto bg-surface-alt p-5">
          <CategorySummary items={categoryItems} />
          <hr className="my-4 border-border" />
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-sans text-subheading font-semibold text-ink">
              Bias flags
            </h3>
            <Badge tone="red">{flags.length}</Badge>
          </div>
          <div className="flex flex-col gap-3">
            {flags.map((flag) => (
              <FlagCard
                key={flag.id}
                category={CATEGORY_LABELS[flag.category]}
                source={sourceLabel(flag.source_stage)}
                original={flag.raw_span}
                explanation={flag.explanation}
                citation={formatCitation(flag.citation)}
              />
            ))}
          </div>
        </aside>
      </div>

      <footer className="flex items-center justify-between border-t border-border bg-surface px-6 py-3.5">
        <Legend />
        <span className="font-sans text-meta text-ink-faint">
          This is your own data — visible only to you.
        </span>
      </footer>
    </main>
  )
}
