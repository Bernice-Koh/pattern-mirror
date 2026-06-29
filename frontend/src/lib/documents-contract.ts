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
