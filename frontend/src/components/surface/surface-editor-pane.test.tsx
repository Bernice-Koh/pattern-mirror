import { createRef } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SurfaceEditorPane } from './surface-editor-pane'
import type { SurfaceEditorHandle } from './surface-editor'
import type { DocumentSession } from './use-document-session'

// The inner editor pulls in TipTap and the analysis wiring; stub it so the pane renders in isolation.
vi.mock('@/components/surface/surface-editor', () => ({
  SurfaceEditor: () => <div data-testid="surface-editor" />,
}))

const SESSION = {
  isLoading: false,
  isReadOnly: true,
  documentId: 'doc-1',
  initialContent: 'Saved copy.',
  title: 'A published JD',
  setTitle: vi.fn(),
  content: 'Saved copy.',
  setContent: vi.fn(),
  saveState: 'idle',
  submitState: 'submitted',
  submit: vi.fn(),
} satisfies DocumentSession

function renderPane(props: { readOnly: boolean; onClose?: () => void }) {
  return render(
    <SurfaceEditorPane
      session={SESSION}
      editorRef={createRef<SurfaceEditorHandle>()}
      documentKindLabel="Job description"
      titlePlaceholder="Untitled"
      readOnly={props.readOnly}
      submitted={props.readOnly}
      onFlagsChange={vi.fn()}
      onApplyRecommendation={vi.fn()}
      onDismissFlag={vi.fn()}
      resolvedFlagIds={new Set()}
      onClose={props.onClose}
    />,
  )
}

describe('SurfaceEditorPane read-only bar', () => {
  it('shows a read-only indicator and a Close control when read-only', () => {
    renderPane({ readOnly: true, onClose: vi.fn() })

    expect(screen.getByText(/read-only/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument()
  })

  it('closes back to the document list on click', () => {
    const onClose = vi.fn()
    renderPane({ readOnly: true, onClose })

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows neither the bar nor a Close control while editable', () => {
    renderPane({ readOnly: false, onClose: vi.fn() })

    expect(screen.queryByText(/read-only/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull()
  })
})
