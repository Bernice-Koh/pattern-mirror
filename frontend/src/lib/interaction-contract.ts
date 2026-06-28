/** Request/response types for the flag-interactions endpoint. A manager's accept or
 *  dismiss of a surfaced flag; "undo" reverses a prior dismiss. Kept in lockstep with the
 *  backend flag_interaction_kind enum. */

export type FlagInteractionKind = 'accept' | 'dismiss' | 'undo'

export interface InteractionRequest {
  kind: FlagInteractionKind
  /** The recommendation taken, on an accept. */
  accepted_alternative?: string | null
}

export interface InteractionResponse {
  id: string
  flag_id: string
  kind: FlagInteractionKind
  /** True when the flag now has an active dismissal suppressing it. */
  dismissed: boolean
}
