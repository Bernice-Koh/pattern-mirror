/** Request/response types for the JD-criteria endpoints (#122): draft criteria from the JD
 *  text with the extraction agent, then confirm the manager's edited set. Kept in lockstep
 *  with the backend models on the /documents router. */

export interface DraftJdCriteriaRequest {
  content: string
}

export interface ConfirmJdCriteriaRequest {
  criteria: string[]
}

export interface JdCriteriaResponse {
  criteria: string[]
}
