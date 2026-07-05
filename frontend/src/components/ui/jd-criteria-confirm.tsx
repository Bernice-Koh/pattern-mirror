import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Modal } from '@/components/ui/modal'
import {
  confirmJdCriteria,
  draftJdCriteria,
  getJdCriteria,
} from '@/lib/jd-criteria-client'

interface JdCriteriaConfirmProps {
  open: boolean
  documentId: string
  content: string
  onClose: () => void
  /** Criteria have been confirmed and persisted; the caller publishes the JD. */
  onConfirmed: () => void
}

type Status = 'loading' | 'ready' | 'saving'

interface Row {
  id: number
  text: string
}

/** The manager-confirm gate for a JD's drift criteria (#122). On open it pre-fills any already
 *  confirmed set, else drafts one from the JD text with the extraction agent; the manager edits
 *  the list, and only the confirmed set is persisted as the Feedback Checkpoint's drift reference.
 *  Drafting is advisory — if it fails the manager enters criteria by hand. */
export function JdCriteriaConfirm({
  open,
  documentId,
  content,
  onClose,
  onConfirmed,
}: Readonly<JdCriteriaConfirmProps>) {
  const [rows, setRows] = useState<Row[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [draftFailed, setDraftFailed] = useState(false)
  const nextId = useRef(0)
  // Read the latest text at draft time without re-drafting on every keystroke behind the modal.
  const contentRef = useRef(content)
  useEffect(() => {
    contentRef.current = content
  }, [content])

  const showRows = useCallback((texts: string[]) => {
    setRows(
      (texts.length > 0 ? texts : ['']).map((text) => ({
        id: nextId.current++,
        text,
      })),
    )
  }, [])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    void (async () => {
      setStatus('loading')
      setDraftFailed(false)

      // Pre-fill an already-confirmed set; a read failure must not block drafting, so it falls
      // through rather than aborting.
      let existing: string[]
      try {
        existing = (await getJdCriteria(documentId)).criteria
      } catch {
        existing = []
      }
      if (cancelled) return
      if (existing.length > 0) {
        showRows(existing)
        setStatus('ready')
        return
      }

      // No confirmed set yet: draft from the JD text. Any failure leaves an empty row to fill in.
      let drafted: string[] = []
      let failed = false
      try {
        drafted = (
          await draftJdCriteria(documentId, { content: contentRef.current })
        ).criteria
      } catch {
        failed = true
      }
      if (cancelled) return
      setDraftFailed(failed)
      showRows(drafted)
      setStatus('ready')
    })()
    return () => {
      cancelled = true
    }
  }, [open, documentId, showRows])

  const confirm = useCallback(async () => {
    setStatus('saving')
    const criteria = rows.map((row) => row.text.trim()).filter(Boolean)
    try {
      await confirmJdCriteria(documentId, { criteria })
      onConfirmed()
    } catch {
      setStatus('ready')
    }
  }, [rows, documentId, onConfirmed])

  function updateRow(id: number, text: string) {
    setRows((current) =>
      current.map((row) => (row.id === id ? { ...row, text } : row)),
    )
  }

  function removeRow(id: number) {
    setRows((current) => current.filter((row) => row.id !== id))
  }

  function addRow() {
    setRows((current) => [...current, { id: nextId.current++, text: '' }])
  }

  const busy = status !== 'ready'

  return (
    <Modal open={open} onClose={onClose} title="Confirm role criteria">
      <h2 className="font-sans text-subheading font-semibold text-ink">
        Confirm role criteria
      </h2>
      <p className="mt-1 font-sans text-body-sm text-ink-faint">
        These become the criteria interview feedback is checked against. We
        drafted them from your job description — edit anything that is off, or
        add your own.
      </p>

      {status === 'loading' ? (
        <p className="mt-6 font-sans text-body-sm text-ink-faint">
          Drafting criteria…
        </p>
      ) : (
        <>
          {draftFailed && (
            <p className="mt-4 font-sans text-meta text-ink-faint">
              We couldn’t draft criteria from the job description — add them
              below.
            </p>
          )}
          <ul className="mt-4 flex flex-col gap-2">
            {rows.map((row) => (
              <li key={row.id} className="flex items-center gap-2">
                <Input
                  value={row.text}
                  onChange={(event) => updateRow(row.id, event.target.value)}
                  placeholder="Describe one criterion"
                  aria-label="Criterion"
                />
                <button
                  type="button"
                  onClick={() => removeRow(row.id)}
                  aria-label="Remove criterion"
                  className="shrink-0 rounded-button px-2 py-1 font-sans text-body-sm text-ink-faint hover:text-ink"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
          <Button variant="ghost" size="sm" className="mt-2" onClick={addRow}>
            Add criterion
          </Button>
        </>
      )}

      <div className="mt-6 flex items-center justify-end gap-2">
        <Button
          variant="secondary"
          size="md"
          onClick={onClose}
          disabled={status === 'saving'}
        >
          Cancel
        </Button>
        <Button variant="primary" size="md" onClick={confirm} disabled={busy}>
          Confirm &amp; publish
        </Button>
      </div>
    </Modal>
  )
}
