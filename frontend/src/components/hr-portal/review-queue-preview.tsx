import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  ReportCard,
  ReportEmptyState,
} from '@/components/hr-portal/report-card'
import { ReviewQueueRow } from '@/components/hr-portal/review-queue-row'
import { getPendingAdditions } from '@/lib/growth-client'

const PREVIEW_COUNT = 4
const REVIEW_PATH = '/hr-portal/dictionary-review'

/** The HR Portal's "words to review" card (#72): a short preview of the pending dictionary
 *  additions, linking into the full review page. Bulk monthly review — the agentic loop has
 *  already filtered the queue (design spec §4). */
export function ReviewQueuePreview() {
  const navigate = useNavigate()
  const additions = useQuery({
    queryKey: ['growth', 'pending-additions'],
    queryFn: getPendingAdditions,
  })

  const items = additions.data ?? []

  return (
    <ReportCard
      title="Words to review"
      caption="New bias-coded phrases waiting for review"
    >
      {items.length === 0 ? (
        <ReportEmptyState message="The review queue is clear" />
      ) : (
        <>
          <div className="-mx-1.5">
            {items.slice(0, PREVIEW_COUNT).map((addition, index) => (
              <div
                key={addition.id}
                className={index === 0 ? '' : 'border-t border-border'}
              >
                <ReviewQueueRow
                  rank={index + 1}
                  phrase={addition.phrase}
                  category={addition.proposed_category}
                  status={addition.status}
                  onReview={() =>
                    navigate({
                      to: REVIEW_PATH,
                      search: { addition: addition.id },
                    })
                  }
                />
              </div>
            ))}
          </div>
          <Link
            to={REVIEW_PATH}
            className="mt-3 inline-block font-sans text-label font-semibold text-red-primary hover:text-red-press"
          >
            Review all ({items.length}) →
          </Link>
        </>
      )}
    </ReportCard>
  )
}
