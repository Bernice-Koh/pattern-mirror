import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import type { DocType } from '@/lib/analyze-contract'
import {
  createDocument,
  DocumentError,
  getDocument,
  submitDocument,
  updateDraft,
} from '@/lib/documents-client'
import { useDebouncedValue } from '@/lib/use-debounced-value'

const AUTOSAVE_DEBOUNCE_MS = 1500
const STORAGE_PREFIX = 'pm:document:'

export type SaveState = 'idle' | 'saving' | 'saved' | 'error'
export type SubmitState = 'idle' | 'submitting' | 'submitted' | 'error'

// localStorage may be unavailable (private mode); remembering the draft id is best-effort.
function readStoredId(docType: DocType): string | null {
  try {
    return localStorage.getItem(`${STORAGE_PREFIX}${docType}`)
  } catch {
    return null
  }
}

function writeStoredId(docType: DocType, id: string): void {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${docType}`, id)
  } catch {
    // ignore
  }
}

function clearStoredId(docType: DocType): void {
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${docType}`)
  } catch {
    // ignore
  }
}

export interface DocumentSession {
  /** False until any stored draft has been restored, so the editor mounts once with its text. */
  isLoading: boolean
  /** The backing document, created on first edit; null until then. */
  documentId: string | null
  /** The restored draft text at load, for the editor's initial (uncontrolled) content. */
  initialContent: string
  title: string
  setTitle: (title: string) => void
  content: string
  setContent: (content: string) => void
  saveState: SaveState
  submitState: SubmitState
  submit: () => void
}

/** Owns one editing session's document: restore a draft on load, create it on the first edit,
 *  autosave title and content on a pause, and submit the final text. Autosave is debounced
 *  separately from analysis — saving never triggers an engine run (design spec §2, §5, §13). */
export function useDocumentSession(docType: DocType): DocumentSession {
  const [isLoading, setIsLoading] = useState(
    () => readStoredId(docType) !== null,
  )
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [initialContent, setInitialContent] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const hasDocument = useRef(false)

  // Restore a remembered draft once on mount; a missing or already-submitted one starts fresh.
  useEffect(() => {
    const storedId = readStoredId(docType)
    if (!storedId) return
    let cancelled = false
    getDocument(storedId)
      .then((document) => {
        if (cancelled) return
        if (document.status !== 'draft') {
          clearStoredId(docType)
          return
        }
        hasDocument.current = true
        setDocumentId(document.id)
        setTitle(document.title ?? '')
        setContent(document.content)
        setInitialContent(document.content)
      })
      .catch((error) => {
        if (!cancelled && error instanceof DocumentError) clearStoredId(docType)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [docType])

  // Create the backing document on the first edit so analysis has a stable id immediately,
  // rather than waiting for the slower autosave debounce.
  useEffect(() => {
    if (isLoading || hasDocument.current) return
    if (content.length === 0 && title.length === 0) return
    hasDocument.current = true
    createDocument({ doc_type: docType })
      .then((document) => {
        setDocumentId(document.id)
        writeStoredId(docType, document.id)
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
    onSuccess: () => clearStoredId(docType),
  })

  const debouncedTitle = useDebouncedValue(title, AUTOSAVE_DEBOUNCE_MS)
  const debouncedContent = useDebouncedValue(content, AUTOSAVE_DEBOUNCE_MS)

  useEffect(() => {
    if (!documentId) return
    saveDraft({
      title: debouncedTitle.length > 0 ? debouncedTitle : null,
      content: debouncedContent,
    })
  }, [documentId, debouncedTitle, debouncedContent, saveDraft])

  const submit = useCallback(() => {
    if (!documentId || submitStatus === 'pending') return
    runSubmit({ content })
  }, [documentId, content, submitStatus, runSubmit])

  const saveState: SaveState =
    saveStatus === 'pending'
      ? 'saving'
      : saveStatus === 'error'
        ? 'error'
        : saveStatus === 'success'
          ? 'saved'
          : 'idle'

  const submitState: SubmitState =
    submitStatus === 'pending'
      ? 'submitting'
      : submitStatus === 'error'
        ? 'error'
        : submitStatus === 'success'
          ? 'submitted'
          : 'idle'

  return {
    isLoading,
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
