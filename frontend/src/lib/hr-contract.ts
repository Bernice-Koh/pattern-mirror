/** Response types for the HR Portal's aggregate-only read endpoints (#70 → #71). Mirrors the
 *  backend's EffectivenessResponse / CalibrationResponse / DictionaryHealthResponse: firm-wide
 *  figures only, never an individual manager's writing. The dashboards are pure presentation. */

import type { DocType } from '@/lib/analyze-contract'
import type { BiasCategory } from '@/lib/patterns-contract'

/** Firm-wide adoption rate within one calendar month (the "over time" view, §11). */
export interface AdoptionByPeriod {
  period: string
  adopted_count: number
  total_count: number
  adoption_rate: number
}

/** Firm-wide adoption rate for one bias category. */
export interface AdoptionByCategory {
  category: BiasCategory
  adopted_count: number
  total_count: number
  adoption_rate: number
}

/** Firm-wide adoption rate for one document type. */
export interface AdoptionByDocType {
  doc_type: DocType
  adopted_count: number
  total_count: number
  adoption_rate: number
}

/** The effectiveness dimension: adoption over time, by category, by document type. */
export interface EffectivenessReport {
  adoption_over_time: AdoptionByPeriod[]
  adoption_by_category: AdoptionByCategory[]
  adoption_by_doc_type: AdoptionByDocType[]
}

/** The dictionary-health dimension. All fields are null until Dictionary Growth (#8). */
export interface DictionaryHealthReport {
  proposal_volume: number | null
  agent_agreement_rate: number | null
  citation_coverage: number | null
  approval_throughput: number | null
}
