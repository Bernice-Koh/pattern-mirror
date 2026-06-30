import { useMemo, useRef, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import {
  CATEGORY_LABELS,
  formatCitation,
  sourceLabel,
  type BiasCategory,
  type CitedFlag,
} from '@/lib/analyze-contract'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CategorySummary } from '@/components/ui/category-summary'
import { Editor } from '@/components/ui/editor'
import { FlagCard } from '@/components/ui/flag-card'
import { Legend } from '@/components/ui/legend'
import { AutosaveStatus } from '@/components/jd-studio/autosave-status'
import { JdEditor, type JdEditorHandle } from '@/components/jd-studio/jd-editor'
import { useDocumentSession } from '@/components/jd-studio/use-document-session'
import { useFlagInteractions } from '@/components/jd-studio/use-flag-interactions'

const SUBMIT_LABELS = {
  idle: 'Publish JD',
  submitting: 'Publishing…',
  submitted: 'Published',
  error: 'Publish JD',
} as const

export function JdStudio() {
  // A document opened from My Documents (#69) arrives as ?doc=<id>; absent for a fresh draft.
  const { doc } = useSearch({ strict: false })
  const session = useDocumentSession('jd', doc)
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

  // Dismissed flags lose their inline underline at once (their span is unchanged); accepted
  // ones clear via the re-analysis their text edit triggers, so only dismissals go here.
  const dismissedFlagIds = useMemo(
    () =>
      new Set(
        [...resolutions.entries()]
          .filter(([, resolution]) => resolution === 'dismissed')
          .map(([id]) => id),
      ),
    [resolutions],
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

  // Hold the editor's mount until any remembered draft is restored, so it initialises once
  // with the restored text rather than flashing empty and overwriting it.
  if (session.isLoading) {
    return <main className="h-[calc(100vh-7rem)] bg-surface" />
  }

  const readOnly = session.isReadOnly
  const submitted = session.submitState === 'submitted' || readOnly

  return (
    <main className="flex h-[calc(100vh-7rem)] flex-col bg-surface">
      <div className="grid min-h-0 flex-1 grid-cols-[58%_42%]">
        <div className="overflow-auto border-r border-border">
          <Editor
            title={session.title}
            onTitleChange={session.setTitle}
            titlePlaceholder="Untitled job description"
            meta={
              <span className="inline-flex items-center gap-1.5">
                <span>
                  Job description · {submitted ? 'submitted' : 'draft'}
                </span>
                {session.saveState !== 'idle' && <span aria-hidden>·</span>}
                <AutosaveStatus state={session.saveState} />
              </span>
            }
          >
            <JdEditor
              ref={editorRef}
              documentId={session.documentId}
              editable={!readOnly}
              initialContent={session.initialContent}
              onTextChange={session.setContent}
              onFlagsChange={setFlags}
              onApplyRecommendation={applyRecommendation}
              onDismissFlag={(flag) => dismiss(flag.id)}
              dismissedFlagIds={dismissedFlagIds}
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
        <div className="flex items-center gap-4">
          <span className="font-sans text-meta text-ink-faint">
            This is your own data — visible only to you.
          </span>
          <Button
            variant="primary"
            size="md"
            onClick={session.submit}
            disabled={
              !session.documentId ||
              session.submitState === 'submitting' ||
              submitted
            }
          >
            {readOnly ? 'Published' : SUBMIT_LABELS[session.submitState]}
          </Button>
        </div>
      </footer>
    </main>
  )
}
