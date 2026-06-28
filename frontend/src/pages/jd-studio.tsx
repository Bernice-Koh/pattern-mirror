import { useMemo, useRef, useState } from 'react'
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
import { JdEditor, type JdEditorHandle } from '@/components/jd-studio/jd-editor'
import { useFlagInteractions } from '@/components/jd-studio/use-flag-interactions'

export function JdStudio() {
  const [title, setTitle] = useState('')
  const [flags, setFlags] = useState<CitedFlag[]>([])
  const editorRef = useRef<JdEditorHandle>(null)
  const { resolutions, accept, dismiss, undo } = useFlagInteractions()

  // Apply writes the chosen phrasing into the document, then logs the acceptance; the
  // text change re-runs analysis, which clears the now-resolved underline.
  function applyRecommendation(flag: CitedFlag, suggestion: string) {
    editorRef.current?.applyRecommendation(flag, suggestion)
    accept(flag.id, suggestion)
  }

  // Accepted flags drop out of the panel; dismissed ones stay, greyed with Undo.
  const visibleFlags = useMemo(
    () => flags.filter((flag) => resolutions.get(flag.id) !== 'accepted'),
    [flags, resolutions],
  )

  const categoryItems = useMemo(() => {
    const counts = new Map<BiasCategory, number>()
    for (const flag of visibleFlags) {
      counts.set(flag.category, (counts.get(flag.category) ?? 0) + 1)
    }
    return [...counts.entries()]
      .map(([category, count]) => ({ label: CATEGORY_LABELS[category], count }))
      .sort((a, b) => b.count - a.count)
  }, [visibleFlags])

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
            <JdEditor
              ref={editorRef}
              docType="jd"
              initialContent=""
              onFlagsChange={setFlags}
              onApplyRecommendation={applyRecommendation}
              onDismissFlag={(flag) => dismiss(flag.id)}
            />
          </Editor>
        </div>

        <aside className="overflow-auto bg-surface-alt p-5">
          <CategorySummary items={categoryItems} />
          <hr className="my-4 border-border" />
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-sans text-subheading font-semibold text-ink">
              Bias flags
            </h3>
            <Badge tone="red">{visibleFlags.length}</Badge>
          </div>
          <div className="flex flex-col gap-3">
            {visibleFlags.map((flag) => (
              <FlagCard
                key={flag.id}
                category={CATEGORY_LABELS[flag.category]}
                source={sourceLabel(flag.source_stage)}
                original={flag.raw_span}
                explanation={flag.explanation}
                citation={formatCitation(flag.citation)}
                suggestions={flag.recommendations?.alternatives ?? []}
                dismissed={resolutions.get(flag.id) === 'dismissed'}
                onApply={(suggestion) => applyRecommendation(flag, suggestion)}
                onDismiss={() => dismiss(flag.id)}
                onUndo={() => undo(flag.id)}
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
