import type { ReactNode } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { Legend } from '@/components/ui/legend'
import { SurfaceEditorPane } from '@/components/surface/surface-editor-pane'
import type { SubmitState } from '@/components/surface/use-document-session'
import type { CheckpointSurface } from '@/components/surface/use-checkpoint-surface'

interface CheckpointLayoutProps {
  surface: CheckpointSurface
  documentKindLabel: string
  titlePlaceholder: string
  /** The reference sub-bar contents (criteria/rubric label + context chips), inside the shared bar. */
  subBar: ReactNode
  /** The right-hand panels (coverage, callouts, observations). */
  aside: ReactNode
  submitLabels: Record<SubmitState, string>
  /** Submit-button label when the document is already submitted (read-only). */
  submittedLabel: string
  footerNote: ReactNode
}

/** The shell shared by the Feedback Checkpoint and Promotion Writeup surfaces: the reference
 *  sub-bar, the editor/aside split, and the non-blocking submit footer with the legend. The two
 *  surfaces supply their own sub-bar and panels; everything structural lives here. */
export function CheckpointLayout({
  surface,
  documentKindLabel,
  titlePlaceholder,
  subBar,
  aside,
  submitLabels,
  submittedLabel,
  footerNote,
}: CheckpointLayoutProps) {
  const { session } = surface
  const navigate = useNavigate()

  return (
    <main className="flex h-[calc(100vh-7rem)] flex-col bg-surface">
      <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-3">
        {subBar}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[58%_42%]">
        <SurfaceEditorPane
          session={session}
          editorRef={surface.editorRef}
          documentKindLabel={documentKindLabel}
          titlePlaceholder={titlePlaceholder}
          readOnly={surface.readOnly}
          submitted={surface.submitted}
          onFlagsChange={surface.setFlags}
          onApplyRecommendation={surface.applyRecommendation}
          onDismissFlag={(flag) => surface.dismiss(flag.id)}
          resolvedFlagIds={surface.resolvedFlagIds}
          onRunComplete={surface.refetchFindings}
          onClose={() => navigate({ to: '/pattern-dashboard' })}
        />

        <aside className="flex flex-col gap-4 overflow-auto bg-surface-alt p-5">
          {aside}
        </aside>
      </div>

      <footer className="border-t border-border bg-surface px-6 py-3.5">
        <div className="flex items-center justify-between">
          <span className="font-sans text-meta text-ink-muted">
            {footerNote}
          </span>
          <Button
            variant="primary"
            size="lg"
            onClick={session.submit}
            disabled={
              !session.documentId ||
              session.submitState === 'submitting' ||
              surface.submitted
            }
          >
            {surface.readOnly
              ? submittedLabel
              : submitLabels[session.submitState]}
          </Button>
        </div>
        <div className="mt-3">
          <Legend />
        </div>
      </footer>
    </main>
  )
}
