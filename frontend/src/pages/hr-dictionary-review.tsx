import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearch } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { ReviewQueueRow } from '@/components/hr-portal/review-queue-row'
import { ReviewCandidateModal } from '@/components/hr-portal/review-candidate-modal'
import { getPendingAdditions } from '@/lib/growth-client'

const PAGE_SIZE = 10

/** The full HR dictionary review queue (#72): every pending addition, paginated, each opening into
 *  a focused review of the four agents' reasoning and the citation. Reached from the HR Portal
 *  "words to review" card; the monthly bulk review the agentic loop has pre-filtered (§4). */
export function HrDictionaryReview() {
  const search = useSearch({ strict: false }) as { addition?: string }
  const additions = useQuery({
    queryKey: ['growth', 'pending-additions'],
    queryFn: getPendingAdditions,
  })
  const items = additions.data ?? []

  const [page, setPage] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(
    search.addition ?? null,
  )

  const selected = items.find((addition) => addition.id === selectedId) ?? null
  const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE))
  const start = page * PAGE_SIZE
  const visible = items.slice(start, start + PAGE_SIZE)

  return (
    <main className="overflow-auto bg-canvas px-10 py-9">
      <div className="mx-auto max-w-3xl">
        <Link
          to="/hr-portal"
          className="font-sans text-label font-semibold text-ink-muted hover:text-ink"
        >
          ← HR Portal
        </Link>
        <h1 className="mt-3 font-serif text-display font-bold text-ink">
          Dictionary review queue
        </h1>
        <p className="mt-2.5 mb-7 font-sans text-body leading-relaxed text-ink-muted">
          New bias-coded phrases the review agents flagged. Approve to add each
          as a dictionary term, or reject and defer.
        </p>

        {additions.isError ? (
          <div className="rounded-card bg-surface p-10 text-center shadow-ring-card">
            <p className="font-sans text-body-sm text-ink-faint">
              Couldn’t load the review queue. Try again.
            </p>
          </div>
        ) : additions.isPending ? (
          <p className="font-sans text-label text-ink-faint">Loading…</p>
        ) : items.length === 0 ? (
          <div className="rounded-card bg-surface p-10 text-center shadow-ring-card">
            <p className="font-sans text-body-sm text-ink-faint">
              The review queue is clear.
            </p>
          </div>
        ) : (
          <>
            <div className="rounded-card bg-surface p-2 shadow-ring-card">
              {visible.map((addition, index) => (
                <div
                  key={addition.id}
                  className={index === 0 ? '' : 'border-t border-border'}
                >
                  <ReviewQueueRow
                    rank={start + index + 1}
                    phrase={addition.phrase}
                    category={addition.proposed_category}
                    status={addition.status}
                    onReview={() => setSelectedId(addition.id)}
                  />
                </div>
              ))}
            </div>

            {pageCount > 1 && (
              <div className="mt-5 flex items-center gap-4">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => current - 1)}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <span className="font-sans text-label text-ink-muted">
                  Page {page + 1} of {pageCount}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={page >= pageCount - 1}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {selected && (
        <ReviewCandidateModal
          addition={selected}
          onClose={() => setSelectedId(null)}
        />
      )}
    </main>
  )
}
