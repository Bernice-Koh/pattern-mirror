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
}: SurfaceEditorPaneProps) {
  return (
    <div className="overflow-auto border-r border-border">
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
