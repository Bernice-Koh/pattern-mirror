import { useEffect, useRef, useState } from 'react'
import type { CitedFlag } from '@/lib/analyze-contract'
import { streamAnalysis } from '@/lib/stream-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'

const STREAM_IDLE_MS = 3000

/** Layer 2 of JD Studio's two-trigger model: after the manager pauses for
 *  STREAM_IDLE_MS, open the SSE pipeline for the latest document and accumulate the
 *  contextual flags it streams in. Resuming typing aborts the in-flight run; the next
 *  pause starts a fresh one, replacing the prior run's flags. Dictionary flags from the
 *  stream are ignored — Layer 1's `/analyze` path already renders those.
 *
 *  The accumulating SSE subscription lives here, in a hook, rather than on TanStack
 *  Query, which models request/response server state (CODE_STYLE: state management).
 *
 *  @param documentId The document to stream, from the latest Layer-1 response; null
 *    until the first dictionary pass returns, which suspends Layer 2.
 *  @param text The editor's current text; its idle pause triggers the run.
 */
export function useFlagStream(
  documentId: string | null,
  text: string,
): CitedFlag[] {
  const [contextualFlags, setContextualFlags] = useState<CitedFlag[]>([])
  const debouncedText = useDebouncedValue(text, STREAM_IDLE_MS)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (!documentId || debouncedText.length === 0) return

    const docId = documentId
    const controller = new AbortController()
    controllerRef.current = controller

    async function consume(): Promise<void> {
      // Reset here, not in the effect body, so a fresh run clears the prior flags
      // without a synchronous setState cascade.
      setContextualFlags([])
      try {
        for await (const event of streamAnalysis(
          { document_id: docId, content: debouncedText },
          controller.signal,
        )) {
          if (
            event.type === 'flag' &&
            event.flag.source_stage === 'contextual'
          ) {
            setContextualFlags((prev) => [...prev, event.flag])
          }
        }
      } catch {
        // A superseded, failed, or aborted run keeps the last painted flags; the next
        // pass replaces them. Surfacing nothing here matches Layer 1's keep-last policy.
      }
    }
    void consume()

    return () => controller.abort()
  }, [documentId, debouncedText])

  // Resuming typing supersedes the in-flight run before the next pause settles.
  useEffect(() => {
    if (controllerRef.current && text !== debouncedText) {
      controllerRef.current.abort()
    }
  }, [text, debouncedText])

  return contextualFlags
}
