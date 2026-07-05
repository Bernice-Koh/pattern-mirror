/** Response type for GET /documents/{id}/promotion-context — the employee, target level, rubric,
 *  and per-criterion peer corroboration the Promotion Writeup renders above the editor. In lockstep
 *  with the backend. */

/** One rubric criterion and whether the employee's peers evidence it, with the peer quote. */
export interface PeerCorroboration {
  criterion: string
  corroborated: boolean
  evidence: string | null
}

export interface PromotionContext {
  role_title: string | null
  subject_id: string | null
  subject_name: string | null
  criteria: string[]
  corroboration: PeerCorroboration[]
}
