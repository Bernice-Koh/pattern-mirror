/** Request/response types for the /documents lifecycle endpoints: create a draft,
 *  restore it, autosave it, and submit it. Kept in lockstep with the backend models. */

import type { DocType } from '@/lib/analyze-contract'

export type DocumentStatus = 'draft' | 'submitted'

export interface DocumentResponse {
  id: string
  doc_type: DocType
  title: string | null
  status: DocumentStatus
  content: string
}

/** A document's metadata for the history listing — no text, just what a row shows. */
export interface DocumentSummary {
  id: string
  doc_type: DocType
  title: string | null
  role_title: string | null
  status: DocumentStatus
  created_at: string
  updated_at: string
  submitted_at: string | null
}

export interface CreateDocumentRequest {
  doc_type: DocType
}

export interface UpdateDraftRequest {
  title: string | null
  content: string
}

export interface SubmitRequest {
  content: string
}
