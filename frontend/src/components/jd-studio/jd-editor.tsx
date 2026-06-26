import { useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, MouseEvent as ReactMouseEvent } from 'react'
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
}

/** The writing surface: a single-paragraph TipTap editor whose text is analysed
 *  on a typing pause, with the returned flags drawn as inline underlines that
 *  reveal their citation on hover. */
export function JdEditor({
  docType,
  initialContent,
  onFlagsChange,
}: JdEditorProps) {
  const [text, setText] = useState(initialContent)
  const [hover, setHover] = useState<HoverState | null>(null)
  const flagsById = useRef<Map<string, CitedFlag>>(new Map())

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

  function handleMouseOver(event: ReactMouseEvent<HTMLDivElement>) {
    const span = (event.target as HTMLElement).closest(
      '.flag-dict, .flag-context',
    )
    if (!(span instanceof HTMLElement)) {
      setHover(null)
      return
    }
    const flag = span.dataset.flagId
      ? flagsById.current.get(span.dataset.flagId)
      : undefined
    if (!flag) return
    const rect = span.getBoundingClientRect()
    setHover({ flag, top: rect.bottom + 6, left: rect.left })
  }

  return (
    <div onMouseOver={handleMouseOver} onMouseLeave={() => setHover(null)}>
      <EditorContent editor={editor} />
      {hover && (
        <FlagPopover
          className="pointer-events-none fixed top-(--pop-top) left-(--pop-left) z-20"
          style={
            {
              '--pop-top': `${hover.top}px`,
              '--pop-left': `${hover.left}px`,
            } as CSSProperties
          }
          category={CATEGORY_LABELS[hover.flag.category]}
          source={sourceLabel(hover.flag.source_stage)}
          explanation={hover.flag.explanation}
          citation={formatCitation(hover.flag.citation)}
        />
      )}
    </div>
  )
}
