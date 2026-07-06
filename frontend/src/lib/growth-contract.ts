/** Response types for the dictionary-growth endpoints (#90 approval, #91 audit) the HR
 *  review-queue surface (#72) calls. Mirrors the backend's PendingAdditionResponse and
 *  ProposalAuditResponse. Its bias-category set is the backend growth enum — deliberately not the
 *  patterns-contract BiasCategory, which carries `relevance` and omits `religion`. */

/** The protected characteristics the four-agent Proposer chooses from — the backend enum exactly. */
export type GrowthBiasCategory =
  | 'gender'
  | 'age'
  | 'race'
  | 'nationality'
  | 'religion'
  | 'disability'
  | 'family_status'

export type CitationSourceType = 'tafep' | 'academic' | 'regulatory' | 'other'

export type DictionaryAdditionStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'deferred'

/** The four growth agents whose arguments the audit replays, in review order. */
export type GrowthAgentName =
  | 'proposer'
  | 'skeptic'
  | 'categorizer'
  | 'citation'

/** The source backing a proposed addition, shown so HR reviews a case, not a bare phrase. */
export interface CitationSummary {
  source_type: CitationSourceType
  title: string
  reference: string
  publication_year: number | null
  finding: string | null
}

/** One phrase queued for the monthly bulk HR review. */
export interface PendingAddition {
  id: string
  proposal_id: string
  phrase: string
  proposed_category: GrowthBiasCategory
  explanation: string
  status: DictionaryAdditionStatus
  created_at: string
  decided_at: string | null
  citation: CitationSummary | null
  /** Contextual-pass flags proposing this phrase firm-wide — its recurrence, and the word-cloud weight. */
  flag_count: number
}

/** One growth agent's logged argument; `output` is the agent's raw structured result. */
export interface AgentArgument {
  agent_name: GrowthAgentName
  model: string
  output: Record<string, unknown>
}

/** The HR decision on an addition that reached the queue. */
export interface AuditDecision {
  status: DictionaryAdditionStatus
  decided_by: string | null
  decided_at: string | null
}

/** The live dictionary row an approval produced, if the chain got that far. */
export interface LiveEntry {
  id: string
  term: string
  active: boolean
}

/** A proposal's full provenance chain: arguments, citation, decision, and live row (#91). */
export interface ProposalAudit {
  proposal_id: string
  phrase: string
  lemma_key: string
  proposed_at: string
  advanced: boolean
  arguments: AgentArgument[]
  citation: CitationSummary | null
  decision: AuditDecision | null
  live_entry: LiveEntry | null
}

/** The three actions HR can take on a queued addition. */
export type GrowthDecision = 'approve' | 'reject' | 'defer'
