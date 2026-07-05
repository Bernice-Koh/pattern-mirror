import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import type { DocType } from '@/lib/analyze-contract'
import {
  createDocument,
  getDocument,
  submitDocument,
  updateDraft,
} from '@/lib/documents-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'

const AUTOSAVE_DEBOUNCE_MS = 1500

export type SaveState = 'idle' | 'saving' | 'saved' | 'error'
export type SubmitState = 'idle' | 'submitting' | 'submitted' | 'error'

type MutationStatus = 'idle' | 'pending' | 'error' | 'success'

// Map react-query's mutation status onto our UI states, so the lookup stays flat and exhaustive.
const SAVE_STATE_BY_STATUS: Record<MutationStatus, SaveState> = {
  idle: 'idle',
  pending: 'saving',
  error: 'error',
  success: 'saved',
}

const SUBMIT_STATE_BY_STATUS: Record<MutationStatus, SubmitState> = {
  idle: 'idle',
  pending: 'submitting',
  error: 'error',
  success: 'submitted',
}

export interface DocumentSession {
  /** False once any opened document has loaded; true only while opening one from My Documents. */
  isLoading: boolean
  /** A submitted document opened from the history list: shown read-only, never autosaved. */
  isReadOnly: boolean
  /** The backing document, created on first edit; null until then. */
  documentId: string | null
  /** The opened document's text at load, for the editor's initial (uncontrolled) content. */
  initialContent: string
  title: string
  setTitle: (title: string) => void
  content: string
  setContent: (content: string) => void
  saveState: SaveState
  submitState: SubmitState
  submit: () => void
}

/** Owns one editing session's document: load an explicitly opened document, create one on the
 *  first edit, autosave title and content on a pause, and submit the final text. Autosave is
 *  debounced separately from analysis — saving never triggers an engine run (design spec §2, §5, §13).
 *
 *  Direct navigation to a surface starts a blank draft. A session loads an existing document only
 *  when one is opened from My Documents (`overrideDocId`, #69) — there is no implicit "resume my
 *  last draft", which is ambiguous once a manager has several. An opened draft resumes editing; an
 *  opened submitted document loads read-only. */
export function useDocumentSession(
  docType: DocType,
  overrideDocId?: string,
): DocumentSession {
  const [isLoading, setIsLoading] = useState(() => overrideDocId != null)
  const [isReadOnly, setIsReadOnly] = useState(false)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [initialContent, setInitialContent] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const hasDocument = useRef(false)

  // Load a document only when one is explicitly opened from My Documents (?doc=). A draft resumes
  // editing; a submitted document opens read-only. A missing/foreign id just leaves a blank editor.
  useEffect(() => {
    if (!overrideDocId) return
    let cancelled = false
    getDocument(overrideDocId)
      .then((document) => {
        if (cancelled) return
        hasDocument.current = true
        setDocumentId(document.id)
        setTitle(document.title ?? '')
        setContent(document.content)
        setInitialContent(document.content)
        setIsReadOnly(document.status === 'submitted')
      })
      .catch(() => {
        // Nothing to restore; the editor stays blank.
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [overrideDocId])

  // Create the backing document on the first edit so analysis has a stable id immediately,
  // rather than waiting for the slower autosave debounce.
  useEffect(() => {
    if (isLoading || hasDocument.current) return
    if (content.length === 0 && title.length === 0) return
    hasDocument.current = true
    createDocument({ doc_type: docType })
      .then((document) => {
        setDocumentId(document.id)
      })
      .catch(() => {
        hasDocument.current = false
      })
  }, [isLoading, docType, content, title])

  const { mutate: saveDraft, status: saveStatus } = useMutation({
    mutationFn: (draft: { title: string | null; content: string }) => {
      if (!documentId) throw new Error('autosave requires a document')
      return updateDraft(documentId, draft)
    },
  })

  const { mutate: runSubmit, status: submitStatus } = useMutation({
    mutationFn: (final: { content: string }) => {
      if (!documentId) throw new Error('submit requires a document')
      return submitDocument(documentId, final)
    },
  })

  const debouncedTitle = useDebouncedValue(title, AUTOSAVE_DEBOUNCE_MS)
  const debouncedContent = useDebouncedValue(content, AUTOSAVE_DEBOUNCE_MS)

  useEffect(() => {
    if (!documentId || isReadOnly) return
    saveDraft({
      title: debouncedTitle.length > 0 ? debouncedTitle : null,
      content: debouncedContent,
    })
  }, [documentId, isReadOnly, debouncedTitle, debouncedContent, saveDraft])

  const submit = useCallback(() => {
    if (!documentId || isReadOnly || submitStatus === 'pending') return
    runSubmit({ content })
  }, [documentId, isReadOnly, content, submitStatus, runSubmit])

  const saveState = SAVE_STATE_BY_STATUS[saveStatus]
  const submitState = SUBMIT_STATE_BY_STATUS[submitStatus]

  return {
    isLoading,
    isReadOnly,
    documentId,
    initialContent,
    title,
    setTitle,
    content,
    setContent,
    saveState,
    submitState,
    submit,
  }
}
