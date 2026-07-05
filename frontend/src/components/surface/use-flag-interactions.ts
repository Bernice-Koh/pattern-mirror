import { useCallback, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { recordInteraction } from '@/lib/interaction-client'
import type {
  FlagInteractionKind,
  InteractionRequest,
} from '@/lib/interaction-contract'

/** How a flag has been resolved in the panel; an unresolved flag has no entry. */
export type FlagResolution = 'accepted' | 'dismissed'

interface MutationArgs {
  flagId: string
  request: InteractionRequest
}

/** Owns the manager's accept/dismiss/undo on flags: it sends the interaction and tracks an
 *  optimistic resolution per flag so the panel updates instantly, rolling back on failure.
 *
 *  The resolution map is local UI state, not server state — the write itself goes through a
 *  TanStack mutation (CODE_STYLE: state management). */
export function useFlagInteractions() {
  const [resolutions, setResolutions] = useState<Map<string, FlagResolution>>(
    new Map(),
  )
  const mutation = useMutation({
    mutationFn: ({ flagId, request }: MutationArgs) =>
      recordInteraction(flagId, request),
  })

  const setResolution = useCallback(
    (flagId: string, resolution: FlagResolution | undefined) => {
      setResolutions((prev) => {
        const next = new Map(prev)
        if (resolution) next.set(flagId, resolution)
        else next.delete(flagId)
        return next
      })
    },
    [],
  )

  const send = useCallback(
    (
      flagId: string,
      kind: FlagInteractionKind,
      optimistic: FlagResolution | undefined,
      accepted_alternative?: string,
    ) => {
      const rollbackTo = resolutions.get(flagId)
      setResolution(flagId, optimistic)
      mutation.mutate(
        { flagId, request: { kind, accepted_alternative } },
        { onError: () => setResolution(flagId, rollbackTo) },
      )
    },
    [resolutions, setResolution, mutation],
  )

  const accept = useCallback(
    (flagId: string, alternative: string) =>
      send(flagId, 'accept', 'accepted', alternative),
    [send],
  )
  const dismiss = useCallback(
    (flagId: string) => send(flagId, 'dismiss', 'dismissed'),
    [send],
  )
  const undo = useCallback(
    (flagId: string) => send(flagId, 'undo', undefined),
    [send],
  )

  return { resolutions, accept, dismiss, undo }
}
