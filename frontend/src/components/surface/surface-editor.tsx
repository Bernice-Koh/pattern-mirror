import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import type {
  CSSProperties,
  FocusEvent as ReactFocusEvent,
  MouseEvent as ReactMouseEvent,
} from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import {
  CATEGORY_LABELS,
  formatCitation,
  sourceLabel,
  type CitedFlag,
} from '@/lib/analyze-contract'
import { analyzeDocument } from '@/lib/analyze-client'
import { listFlags } from '@/lib/flags-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'
import { Button } from '@/components/ui/button'
import { FlagPopover } from '@/components/ui/flag-popover'
import {
  applyFlags,
  FlagDecorations,
} from '@/components/surface/flag-decorations'
import { useFlagStream } from '@/components/surface/use-flag-stream'

const ANALYZE_DEBOUNCE_MS = 400

/** Circular arrow marking the re-check action — a fresh pass after a major rewrite. */
function RecheckIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5" />
    </svg>
  )
}

interface HoverState {
  flag: CitedFlag
  top: number
  left: number
}

export interface SurfaceEditorProps {
  /** The backing document, created on first edit; null suspends Layer 1 and Layer 2 until then. */
  documentId: string | null
  /** False opens the saved text read-only (a submitted document from My Documents): no editing,
   *  no analysis, no re-check. Defaults to true. */
  editable?: boolean
  initialContent: string
  /** Report the editor's text up so the session can autosave and submit it. */
  onTextChange?: (text: string) => void
  onFlagsChange?: (flags: CitedFlag[]) => void
  /** Apply a recommendation from the hover popover (replace the span + log the accept). */
  onApplyRecommendation?: (flag: CitedFlag, suggestion: string) => void
  /** Dismiss a flag from the hover popover. */
  onDismissFlag?: (flag: CitedFlag) => void
  /** Flag ids the manager has resolved (accepted or dismissed); their underline and hover
   *  popover clear at once, rather than lingering until the re-scan an accept's text edit
   *  triggers settles a few seconds later. */
  resolvedFlagIds?: ReadonlySet<string>
  /** Fired with the run id when a streaming/re-check run completes, so a surface can read side
   *  outputs the flag stream doesn't carry (Feedback Checkpoint's drift findings). */
  onRunComplete?: (runId: string) => void
}

const POPOVER_CLOSE_MS = 100

/** Imperative surface the flag panel uses to apply a recommendation into the text. */
export interface SurfaceEditorHandle {
  applyRecommendation: (flag: CitedFlag, replacement: string) => void
}

/** The shared writing surface behind JD Studio, Feedback Checkpoint, and Promotion Writeup:
 *  a single-paragraph TipTap editor whose text is analysed on a typing pause, with the
 *  returned flags drawn as inline underlines that reveal their citation on hover. */
export const SurfaceEditor = forwardRef<
  SurfaceEditorHandle,
  SurfaceEditorProps
>(function SurfaceEditor(
  {
    documentId,
    editable = true,
    initialContent,
    onTextChange,
    onFlagsChange,
    onApplyRecommendation,
    onDismissFlag,
    resolvedFlagIds,
    onRunComplete,
  },
  ref,
) {
  const [text, setText] = useState(initialContent)
  const [hover, setHover] = useState<HoverState | null>(null)
  const flagsById = useRef<Map<string, CitedFlag>>(new Map())
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // On open a document shows its persisted flags; the live layers take over only once the manager
  // edits or re-checks, so a reopened draft skips a wasteful re-run and a submitted document shows
  // its flags at all (its live layers stay suspended). `liveActive` latches on and never reverts.
  const [liveActive, setLiveActive] = useState(false)
  const liveActiveRef = useRef(false)
  const initialContentRef = useRef(initialContent)
  useEffect(() => {
    initialContentRef.current = initialContent
  }, [initialContent])
  const goLive = useCallback(() => {
    if (!liveActiveRef.current) {
      liveActiveRef.current = true
      setLiveActive(true)
    }
  }, [])

  // Read-only suspends both analysis layers: a submitted document is shown as saved, not re-run.
  const activeDocumentId = editable ? documentId : null

  const editor = useEditor({
    editable,
    extensions: [StarterKit, FlagDecorations],
    content: initialContent,
    editorProps: {
      attributes: { class: 'jd-prose' },
      handleKeyDown: (_view, event) => event.key === 'Enter',
    },
    onUpdate: ({ editor }) => {
      const next = editor.getText()
      setText(next)
      // A real change (not the restored text re-emitted) hands the surface to the live layers.
      if (next !== initialContentRef.current) goLive()
    },
  })

  const debouncedText = useDebouncedValue(text, ANALYZE_DEBOUNCE_MS)

  // Re-hydrate the last run's surfaced flags on open; disabled once live, which keeps the cached
  // result from overwriting live flags. Any failure falls back to no flags (the editor's policy).
  const { data: storedFlags } = useQuery({
    queryKey: ['stored-flags', documentId],
    queryFn: () => {
      if (!documentId) throw new Error('stored flags require a document')
      return listFlags(documentId)
    },
    enabled: !!documentId && !liveActive,
  })

  const { data } = useQuery({
    queryKey: ['analyze', activeDocumentId, debouncedText],
    queryFn: ({ signal }) => {
      // enabled gates this on a non-null documentId; the guard narrows the type.
      if (!activeDocumentId) throw new Error('analyze requires a document')
      return analyzeDocument(
        { document_id: activeDocumentId, content: debouncedText },
        signal,
      )
    },
    enabled: !!activeDocumentId && debouncedText.length > 0 && liveActive,
    placeholderData: keepPreviousData,
  })

  // Layer 2 streams its contextual flags off the session's document; a re-check re-runs
  // that same stream on demand into the same accumulator. Its automatic pass waits for `liveActive`.
  const { contextualFlags, recheck, isRechecking } = useFlagStream(
    activeDocumentId,
    text,
    onRunComplete,
    liveActive,
  )

  // Before the first edit/re-check, the panel is the re-hydrated set; after, the live layers own it.
  const flags = useMemo(
    () =>
      liveActive
        ? [...(data?.flags ?? []), ...contextualFlags]
        : (storedFlags ?? []),
    [liveActive, data, contextualFlags, storedFlags],
  )

  // A manual re-check is a live action even before any edit, so it hands over to the live layers.
  const handleRecheck = useCallback(() => {
    goLive()
    recheck()
  }, [goLive, recheck])

  // Resolved flags drop out of the editor's underlines and hover map at once; the panel
  // keeps dismissed ones (greyed, with Undo), but a stale underline never lingers here.
  const decoratedFlags = useMemo(
    () => flags.filter((flag) => !resolvedFlagIds?.has(flag.id)),
    [flags, resolvedFlagIds],
  )

  useEffect(() => {
    if (!editor) return
    flagsById.current = new Map(decoratedFlags.map((flag) => [flag.id, flag]))
    applyFlags(editor.view, decoratedFlags)
  }, [editor, decoratedFlags])

  useEffect(() => {
    onTextChange?.(text)
  }, [text, onTextChange])

  useEffect(() => {
    onFlagsChange?.(flags)
  }, [flags, onFlagsChange])

  useImperativeHandle(
    ref,
    () => ({
      applyRecommendation(flag, replacement) {
        if (!editor) return
        const from = flag.start_offset + 1
        const to = flag.end_offset + 1
        if (from < 1 || to > editor.state.doc.content.size || from >= to) return
        // Only replace when the span still reads as flagged, so a stale offset is a no-op.
        if (editor.state.doc.textBetween(from, to) !== flag.raw_span) return
        editor.chain().focus().insertContentAt({ from, to }, replacement).run()
      },
    }),
    [editor],
  )

  function cancelClose() {
    if (closeTimer.current !== null) {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }

  function scheduleClose() {
    cancelClose()
    closeTimer.current = setTimeout(() => setHover(null), POPOVER_CLOSE_MS)
  }

  // Discard a pending close on unmount so a fired timer never sets state late.
  useEffect(
    () => () => {
      if (closeTimer.current !== null) clearTimeout(closeTimer.current)
    },
    [],
  )

  function handleHover(
    event: ReactMouseEvent<HTMLDivElement> | ReactFocusEvent<HTMLDivElement>,
  ) {
    const target = event.target as HTMLElement
    const span = target.closest('.flag-dict, .flag-context')
    if (span instanceof HTMLElement) {
      const flag = span.dataset.flagId
        ? flagsById.current.get(span.dataset.flagId)
        : undefined
      if (!flag) return
      cancelClose()
      if (hover?.flag.id === flag.id) return
      const rect = span.getBoundingClientRect()
      setHover({ flag, top: rect.bottom + 6, left: rect.left })
      return
    }
    // Moving onto the popover keeps it open; anywhere else schedules a close so the
    // bridge survives the gap between the underline and the popover.
    if (target.closest('[role="dialog"]')) {
      cancelClose()
      return
    }
    scheduleClose()
  }

  return (
    <div
      onMouseOver={handleHover}
      onFocus={handleHover}
      onMouseLeave={scheduleClose}
      onBlur={scheduleClose}
    >
      {editable && (
        <div className="mb-2 flex justify-end">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRecheck}
            disabled={!documentId || isRechecking}
          >
            <RecheckIcon />
            {isRechecking ? 'Re-checking…' : 'Re-check'}
          </Button>
        </div>
      )}
      <EditorContent editor={editor} />
      {hover && (
        <FlagPopover
          key={hover.flag.id}
          className="fixed top-(--pop-top) left-(--pop-left) z-20"
          style={
            {
              '--pop-top': `${hover.top}px`,
              '--pop-left': `${hover.left}px`,
            } as CSSProperties
          }
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
          category={CATEGORY_LABELS[hover.flag.category]}
          source={sourceLabel(hover.flag.source_stage)}
          explanation={hover.flag.explanation}
          citation={formatCitation(hover.flag.citation)}
          suggestions={hover.flag.recommendations?.alternatives ?? []}
          onApply={(suggestion) => {
            onApplyRecommendation?.(hover.flag, suggestion)
            setHover(null)
          }}
          onDismiss={() => {
            onDismissFlag?.(hover.flag)
            setHover(null)
          }}
        />
      )}
    </div>
  )
})
