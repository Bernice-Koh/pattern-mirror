/** Response types for the /patterns read endpoint (#66 → #67). Mirrors the backend's
 *  PatternReportResponse: both gated pattern families for the signed-in manager. The dashboard
 *  is pure presentation — these carry structured facts, never a pre-written sentence. */

export type PatternMode = 'per_role' | 'across_time'

/** Canonical bias taxonomy, in lockstep with the backend BiasCategory enum. */
export type BiasCategory =
  | 'gender'
  | 'age'
  | 'nationality'
  | 'race'
  | 'disability'
  | 'family_status'
  | 'relevance'

/** A coded term correlating with subject gender beyond chance, with its source docs for drill-down. */
export interface WritingPattern {
  mode: PatternMode
  term: string
  category: BiasCategory
  dimension: string
  group_counts: Record<string, number>
  supporting_count: number
  p_value: number
  role_title: string | null
  document_ids: string[]
}

/** A bias category the manager adopts or rejects at a significantly different rate (Layer 2, #68). */
export interface DecisionPattern {
  category: BiasCategory
  adopted_count: number
  rejected_count: number
  total_count: number
  adoption_rate: number
  p_value: number
  document_ids: string[]
}

/** The manager's overall adoption rate within one calendar month (the "over time" view, #68). */
export interface AdoptionTrendPoint {
  period: string
  adopted_count: number
  total_count: number
  adoption_rate: number
}

export interface PatternReport {
  writing_patterns: WritingPattern[]
  decision_patterns: DecisionPattern[]
  adoption_trend: AdoptionTrendPoint[]
}
