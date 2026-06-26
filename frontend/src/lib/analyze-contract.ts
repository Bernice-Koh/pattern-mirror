/** Request/response types for the /analyze endpoint, shared by the mock and the
 *  live engine so either can drive the editor unchanged. */

export type DocType = 'jd' | 'feedback' | 'promotion'

/** Kept in lockstep with the backend bias_category enum. */
export type BiasCategory =
  | 'gender'
  | 'age'
  | 'race'
  | 'nationality'
  | 'religion'
  | 'disability'
  | 'family_status'

export type Severity = 'low' | 'medium' | 'high'

export type FlagSourceStage = 'dictionary' | 'contextual'

export type CitationSourceType = 'tafep' | 'academic' | 'regulatory' | 'other'

export interface Citation {
  source_type: CitationSourceType
  title: string
  reference: string
  publication_year: number | null
  finding: string | null
}

export interface CitedFlag {
  id: string
  source_stage: FlagSourceStage
  category: BiasCategory
  severity: Severity
  raw_span: string
  start_offset: number
  end_offset: number
  explanation: string
  citation: Citation
}

export interface AnalyzeRequest {
  doc_type: DocType
  content: string
}

export interface AnalyzeResponse {
  document_id: string
  analysis_run_id: string
  content_hash: string
  flags: CitedFlag[]
}

export const CATEGORY_LABELS: Record<BiasCategory, string> = {
  gender: 'Gender-coded',
  age: 'Age-coded',
  race: 'Race',
  nationality: 'Nationality',
  religion: 'Religion',
  disability: 'Disability',
  family_status: 'Family status',
}

/** Human label for a flag's origin, shared by the popover and the flag cards. */
export function sourceLabel(stage: FlagSourceStage): string {
  return stage === 'contextual' ? 'AI pass' : 'dictionary'
}

/** One-line evidence string for the flag popover and cards. */
export function formatCitation(citation: Citation): string {
  const parts = [citation.reference || citation.title]
  if (citation.publication_year) parts.push(String(citation.publication_year))
  return parts.join(' · ')
}
