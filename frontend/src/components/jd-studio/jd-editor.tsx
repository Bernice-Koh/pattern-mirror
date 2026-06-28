import {
  forwardRef,
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
  type DocType,
} from '@/lib/analyze-contract'
import { analyzeDocument } from '@/lib/analyze-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'
import { FlagPopover } from '@/components/ui/flag-popover'
import {
  applyFlags,
  FlagDecorations,
} from '@/components/jd-studio/flag-decorations'
import { useFlagStream } from '@/components/jd-studio/use-flag-stream'

const ANALYZE_DEBOUNCE_MS = 400

interface HoverState {
  flag: CitedFlag
  top: number
  left: number
}

export interface JdEditorProps {
  docType: DocType
  initialContent: string
  onFlagsChange?: (flags: CitedFlag[]) => void
  /** Apply a recommendation from the hover popover (replace the span + log the accept). */
  onApplyRecommendation?: (flag: CitedFlag, suggestion: string) => void
  /** Dismiss a flag from the hover popover. */
  onDismissFlag?: (flag: CitedFlag) => void
}

const POPOVER_CLOSE_MS = 100

/** Imperative surface the flag panel uses to apply a recommendation into the text. */
export interface JdEditorHandle {
  applyRecommendation: (flag: CitedFlag, replacement: string) => void
}

/** The writing surface: a single-paragraph TipTap editor whose text is analysed
 *  on a typing pause, with the returned flags drawn as inline underlines that
 *  reveal their citation on hover. */
export const JdEditor = forwardRef<JdEditorHandle, JdEditorProps>(
  function JdEditor(
    {
      docType,
      initialContent,
      onFlagsChange,
      onApplyRecommendation,
      onDismissFlag,
    },
    ref,
  ) {
    const [text, setText] = useState(initialContent)
    const [hover, setHover] = useState<HoverState | null>(null)
    const flagsById = useRef<Map<string, CitedFlag>>(new Map())
    const closeTimer = useRef<number | null>(null)

    const editor = useEditor({
      extensions: [StarterKit, FlagDecorations],
      content: initialContent,
      editorProps: {
        attributes: { class: 'jd-prose' },
        handleKeyDown: (_view, event) => event.key === 'Enter',
      },
      onUpdate: ({ editor }) => setText(editor.getText()),
    })

    const debouncedText = useDebouncedValue(text, ANALYZE_DEBOUNCE_MS)

    const { data } = useQuery({
      queryKey: ['analyze', docType, debouncedText],
      queryFn: ({ signal }) =>
        analyzeDocument({ doc_type: docType, content: debouncedText }, signal),
      enabled: debouncedText.length > 0,
      placeholderData: keepPreviousData,
    })

    // Layer 2 streams its contextual flags off the document Layer 1 just persisted.
    const contextualFlags = useFlagStream(data?.document_id ?? null, text)

    const flags = useMemo(
      () => [...(data?.flags ?? []), ...contextualFlags],
      [data, contextualFlags],
    )

    useEffect(() => {
      if (!editor) return
      flagsById.current = new Map(flags.map((flag) => [flag.id, flag]))
      applyFlags(editor.view, flags)
      onFlagsChange?.(flags)
    }, [editor, flags, onFlagsChange])

    useImperativeHandle(
      ref,
      () => ({
        applyRecommendation(flag, replacement) {
          if (!editor) return
          const from = flag.start_offset + 1
          const to = flag.end_offset + 1
          if (from < 1 || to > editor.state.doc.content.size || from >= to)
            return
          // Only replace when the span still reads as flagged, so a stale offset is a no-op.
          if (editor.state.doc.textBetween(from, to) !== flag.raw_span) return
          editor
            .chain()
            .focus()
            .insertContentAt({ from, to }, replacement)
            .run()
        },
      }),
      [editor],
    )

    function cancelClose() {
      if (closeTimer.current !== null) {
        window.clearTimeout(closeTimer.current)
        closeTimer.current = null
      }
    }

    function scheduleClose() {
      cancelClose()
      closeTimer.current = window.setTimeout(
        () => setHover(null),
        POPOVER_CLOSE_MS,
      )
    }

    // Discard a pending close on unmount so a fired timer never sets state late.
    useEffect(
      () => () => {
        if (closeTimer.current !== null) window.clearTimeout(closeTimer.current)
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
  },
)
