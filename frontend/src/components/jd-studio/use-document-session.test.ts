import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import {
  createDocument,
  getDocument,
  submitDocument,
  updateDraft,
} from '@/lib/documents-client'
import { useDocumentSession } from './use-document-session'

vi.mock('@/lib/documents-client', () => ({
  DocumentError: class DocumentError extends Error {},
  createDocument: vi.fn(),
  getDocument: vi.fn(),
  updateDraft: vi.fn(),
  submitDocument: vi.fn(),
}))

const createDocumentMock = vi.mocked(createDocument)
const getDocumentMock = vi.mocked(getDocument)
const updateDraftMock = vi.mocked(updateDraft)
const submitDocumentMock = vi.mocked(submitDocument)

function draft(
  overrides: Partial<{
    id: string
    title: string | null
    content: string
  }> = {},
) {
  return {
    id: overrides.id ?? 'doc-1',
    doc_type: 'jd' as const,
    title: overrides.title ?? null,
    status: 'draft' as const,
    content: overrides.content ?? '',
  }
}

function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    QueryClientProvider,
    { client: new QueryClient() },
    children,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  createDocumentMock.mockResolvedValue(draft())
  updateDraftMock.mockResolvedValue(draft())
  submitDocumentMock.mockResolvedValue({ ...draft(), status: 'submitted' })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useDocumentSession', () => {
  it('creates the backing document on the first edit', async () => {
    const { result } = renderHook(() => useDocumentSession('jd'), { wrapper })

    act(() => result.current.setContent('We want a digital native.'))

    await waitFor(() => expect(result.current.documentId).toBe('doc-1'))
    expect(createDocumentMock).toHaveBeenCalledExactlyOnceWith({
      doc_type: 'jd',
    })
    expect(localStorage.getItem('pm:document:jd')).toBe('doc-1')
  })

  it('autosaves title and content after a pause, without running analysis', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useDocumentSession('jd'), { wrapper })

    await act(async () => {
      result.current.setContent('We want a digital native.')
      result.current.setTitle('Senior Engineer')
      await vi.advanceTimersByTimeAsync(0)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500)
    })

    expect(updateDraftMock).toHaveBeenLastCalledWith('doc-1', {
      title: 'Senior Engineer',
      content: 'We want a digital native.',
    })
  })

  it('submits the current text and reports the submitted state', async () => {
    const { result } = renderHook(() => useDocumentSession('jd'), { wrapper })
    act(() => result.current.setContent('final text'))
    await waitFor(() => expect(result.current.documentId).toBe('doc-1'))

    act(() => result.current.submit())

    await waitFor(() => expect(result.current.submitState).toBe('submitted'))
    expect(submitDocumentMock).toHaveBeenCalledWith('doc-1', {
      content: 'final text',
    })
  })

  it('opens a draft by id without creating a new document', async () => {
    getDocumentMock.mockResolvedValue(
      draft({ id: 'doc-42', title: 'Opened', content: 'opened text' }),
    )

    const { result } = renderHook(() => useDocumentSession('jd', 'doc-42'), {
      wrapper,
    })
    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(getDocumentMock).toHaveBeenCalledWith('doc-42')
    expect(result.current.documentId).toBe('doc-42')
    expect(result.current.initialContent).toBe('opened text')
    expect(result.current.isReadOnly).toBe(false)
    expect(createDocumentMock).not.toHaveBeenCalled()
  })

  it('opens a submitted document read-only and never submits it', async () => {
    getDocumentMock.mockResolvedValue({
      ...draft({ id: 'doc-7', content: 'final text' }),
      status: 'submitted' as const,
    })

    const { result } = renderHook(() => useDocumentSession('jd', 'doc-7'), {
      wrapper,
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isReadOnly).toBe(true)

    act(() => result.current.submit())
    expect(submitDocumentMock).not.toHaveBeenCalled()
  })

  it('restores a remembered draft on load', async () => {
    localStorage.setItem('pm:document:jd', 'doc-9')
    getDocumentMock.mockResolvedValue(
      draft({ id: 'doc-9', title: 'Restored role', content: 'restored text' }),
    )

    const { result } = renderHook(() => useDocumentSession('jd'), { wrapper })
    expect(result.current.isLoading).toBe(true)

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.documentId).toBe('doc-9')
    expect(result.current.title).toBe('Restored role')
    expect(result.current.initialContent).toBe('restored text')
    expect(createDocumentMock).not.toHaveBeenCalled()
  })
})
