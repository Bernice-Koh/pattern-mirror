import type { RefObject } from 'react'
import type { CitedFlag } from '@/lib/analyze-contract'
import { Editor } from '@/components/ui/editor'
import { AutosaveStatus } from '@/components/surface/autosave-status'
import {
  SurfaceEditor,
  type SurfaceEditorHandle,
} from '@/components/surface/surface-editor'
import type { DocumentSession } from '@/components/surface/use-document-session'

interface SurfaceEditorPaneProps {
  session: DocumentSession
  editorRef: RefObject<SurfaceEditorHandle | null>
  /** Document-kind label shown in the editor meta, e.g. "Interview feedback". */
  documentKindLabel: string
  titlePlaceholder: string
  readOnly: boolean
  submitted: boolean
  onFlagsChange: (flags: CitedFlag[]) => void
  onApplyRecommendation: (flag: CitedFlag, suggestion: string) => void
  onDismissFlag: (flag: CitedFlag) => void
  resolvedFlagIds: Set<string>
  /** Called when a full engine run completes; the checkpoint surfaces refetch drift on it. */
  onRunComplete?: (runId: string) => void
  /** Close a read-only (submitted) document, returning to My Documents. Absent while editable. */
  onClose?: () => void
}

/** The X marking the close action on a read-only document. */
function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

/** The read-only bar over a submitted document: it reads as locked, with an X that closes back to
 *  the list. A submitted document is never edited again, so the surface is shown, not re-opened. */
function ReadOnlyBar({ onClose }: Readonly<{ onClose?: () => void }>) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-surface-alt px-8 py-2.5">
      <span className="font-sans text-meta font-semibold tracking-wide text-ink-muted uppercase">
        Read-only · published
      </span>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="inline-flex size-7 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-canvas hover:text-ink"
        >
          <CloseIcon />
        </button>
      )}
    </div>
  )
}

/** The left editor column shared by every writing surface: the titled editor, its draft/submitted
 *  meta with autosave status, and the flag-aware `SurfaceEditor`. Surfaces differ only in the labels
 *  and whether they listen for run completion. */
export function SurfaceEditorPane({
  session,
  editorRef,
  documentKindLabel,
  titlePlaceholder,
  readOnly,
  submitted,
  onFlagsChange,
  onApplyRecommendation,
  onDismissFlag,
  resolvedFlagIds,
  onRunComplete,
  onClose,
}: SurfaceEditorPaneProps) {
  return (
    <div className="overflow-auto border-r border-border">
      {readOnly && <ReadOnlyBar onClose={onClose} />}
      <Editor
        title={session.title}
        onTitleChange={session.setTitle}
        titlePlaceholder={titlePlaceholder}
        meta={
          <span className="inline-flex items-center gap-1.5">
            <span>
              {documentKindLabel} · {submitted ? 'submitted' : 'draft'}
            </span>
            {session.saveState !== 'idle' && <span aria-hidden>·</span>}
            <AutosaveStatus state={session.saveState} />
          </span>
        }
      >
        <SurfaceEditor
          ref={editorRef}
          documentId={session.documentId}
          editable={!readOnly}
          initialContent={session.initialContent}
          onTextChange={session.setContent}
          onFlagsChange={onFlagsChange}
          onApplyRecommendation={onApplyRecommendation}
          onDismissFlag={onDismissFlag}
          resolvedFlagIds={resolvedFlagIds}
          onRunComplete={onRunComplete}
        />
      </Editor>
    </div>
  )
}
