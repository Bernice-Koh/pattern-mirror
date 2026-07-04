import { useCallback, useEffect, useRef, useState } from 'react'
import type { CitedFlag } from '@/lib/analyze-contract'
import { recheckAnalysis, streamAnalysis } from '@/lib/stream-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'

const STREAM_IDLE_MS = 3000

/** Layer 2 of JD Studio's two-trigger model, plus the manual re-check (design spec §3, §12).
 *
 *  After the manager pauses for STREAM_IDLE_MS the contextual pipeline streams in via SSE;
 *  `recheck` runs the same pipeline on demand, first clearing the document's dismissals so
 *  previously-dismissed contextual flags re-surface. Both feed one accumulator, so a re-check
 *  result behaves like any other contextual pass — applying or dismissing one flag leaves the
 *  rest in place, and the next typing pause replaces the set. Dictionary flags are ignored
 *  here; Layer 1's `/analyze` path renders those.
 *
 *  The accumulating SSE subscription lives in a hook, not on TanStack Query, which models
 *  request/response server state (CODE_STYLE: state management).
 *
 *  @param documentId The document to stream, from the latest Layer-1 response; null until the
 *    first dictionary pass returns, which suspends Layer 2 and disables re-check.
 *  @param text The editor's current text; its idle pause triggers the automatic run, and its
 *    current value is what a re-check analyses.
 *  @param onRunComplete Fired with the run id when a run reaches its terminal `done` event, so a
 *    surface can read side outputs the stream doesn't carry (Feedback Checkpoint's drift findings).
 *  @param autoRun Gates only the automatic typing-pause run: false suspends it so a reopened
 *    document shows its re-hydrated flags rather than paying a fresh contextual pass on open (#130).
 *    `recheck` stays available regardless, so a manual re-check still works before any edit.
 *  @returns The accumulated contextual flags, a `recheck` trigger, and `isRechecking`.
 */
export function useFlagStream(
  documentId: string | null,
  text: string,
  onRunComplete?: (runId: string) => void,
  autoRun = true,
): {
  contextualFlags: CitedFlag[]
  recheck: () => void
  isRechecking: boolean
} {
  const [contextualFlags, setContextualFlags] = useState<CitedFlag[]>([])
  const [isRechecking, setIsRechecking] = useState(false)
  const debouncedText = useDebouncedValue(text, STREAM_IDLE_MS)
  const controllerRef = useRef<AbortController | null>(null)
  // Held in a ref so a fresh callback identity never re-subscribes the stream effect.
  const onRunCompleteRef = useRef(onRunComplete)
  useEffect(() => {
    onRunCompleteRef.current = onRunComplete
  }, [onRunComplete])

  useEffect(() => {
    if (!documentId || debouncedText.length === 0 || !autoRun) return

    const docId = documentId
    const controller = new AbortController()
    controllerRef.current = controller

    async function consume(): Promise<void> {
      // Hold the prior run's flags until this one delivers its replacement, so a
      // re-run triggered by accepting a single flag never blinks the panel empty.
      const next: CitedFlag[] = []
      let replaced = false
      try {
        for await (const event of streamAnalysis(
          { document_id: docId, content: debouncedText },
          controller.signal,
        )) {
          if (
            event.type === 'flag' &&
            event.flag.source_stage === 'contextual'
          ) {
            next.push(event.flag)
            setContextualFlags([...next])
            replaced = true
          } else if (event.type === 'done') {
            onRunCompleteRef.current?.(event.analysis_run_id)
          }
        }
        // A clean run that found nothing still clears the now-stale set.
        if (!replaced) setContextualFlags([])
      } catch {
        // A superseded, failed, or aborted run keeps the last painted flags; the next
        // pass replaces them. Surfacing nothing here matches Layer 1's keep-last policy.
      }
    }
    void consume()

    return () => controller.abort()
  }, [documentId, debouncedText, autoRun])

  // Resuming typing supersedes the in-flight run before the next pause settles.
  useEffect(() => {
    if (controllerRef.current && text !== debouncedText) {
      controllerRef.current.abort()
    }
  }, [text, debouncedText])

  const recheck = useCallback(() => {
    if (!documentId) return
    const docId = documentId
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller

    async function consume(): Promise<void> {
      setContextualFlags([])
      setIsRechecking(true)
      try {
        for await (const event of recheckAnalysis(
          docId,
          text,
          controller.signal,
        )) {
          if (
            event.type === 'flag' &&
            event.flag.source_stage === 'contextual'
          ) {
            setContextualFlags((prev) => [...prev, event.flag])
          } else if (event.type === 'done') {
            onRunCompleteRef.current?.(event.analysis_run_id)
          }
        }
      } catch {
        // Aborted or failed: keep whatever surfaced; the next pass replaces it.
      } finally {
        if (controllerRef.current === controller) setIsRechecking(false)
      }
    }
    void consume()
  }, [documentId, text])

  return { contextualFlags, recheck, isRechecking }
}
