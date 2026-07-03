/** Response type for GET /documents/{id}/feedback-context — the candidate, role, and reference
 *  JD criteria the Feedback Checkpoint renders above the editor. In lockstep with the backend. */

export interface FeedbackContext {
  role_title: string | null
  subject_name: string | null
  criteria: string[]
}
