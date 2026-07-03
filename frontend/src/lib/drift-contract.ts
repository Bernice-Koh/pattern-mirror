/** Types for the drift-findings API (#64/#65): how much of a document's reference corpus the
 *  writing covers. One corpus-agnostic shape shared by Feedback Checkpoint and Promotion Writeup —
 *  the surface maps `reference_kind` to its own label. Kept in lockstep with backend api/drift.py. */

export type ReferenceKind = 'jd_criteria' | 'peer_feedback'

export type DriftInteractionKind = 'dismiss' | 'undo'

/** One reference criterion and whether the document addresses it. Evidence is present only on an
 *  addressed criterion. */
export interface DriftFinding {
  id: string
  reference_kind: ReferenceKind
  criterion: string
  addressed: boolean
  evidence: string | null
  evidence_start: number | null
  evidence_end: number | null
}

export interface DriftInteractionResponse {
  id: string
  finding_id: string
  kind: DriftInteractionKind
  dismissed: boolean
}
