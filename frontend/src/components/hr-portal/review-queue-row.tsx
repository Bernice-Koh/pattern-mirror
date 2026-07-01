import { Badge } from '@/components/ui/badge'
import type {
  DictionaryAdditionStatus,
  GrowthBiasCategory,
} from '@/lib/growth-contract'

interface ReviewQueueRowProps {
  rank: number
  phrase: string
  category: GrowthBiasCategory
  status?: DictionaryAdditionStatus
  onReview: () => void
}

/** One row in the dictionary review queue: rank, phrase, proposed category, and a Review action.
 *  Presentational — the queue data and the decision flow live in the page and the modal. */
export function ReviewQueueRow({
  rank,
  phrase,
  category,
  status,
  onReview,
}: Readonly<ReviewQueueRowProps>) {
  return (
    <div className="flex items-center gap-4 rounded-md px-3.5 py-3 transition-colors hover:bg-canvas">
      <span className="w-4 flex-none font-sans text-meta text-ink-faint">
        {rank}
      </span>
      <span className="font-sans text-body-sm font-semibold text-ink">
        {phrase}
      </span>
      <Badge tone="neutral" className="capitalize">
        {category.replace('_', ' ')}
      </Badge>
      {status === 'deferred' && (
        <span className="font-sans text-meta text-ink-faint">Deferred</span>
      )}
      <button
        type="button"
        onClick={onReview}
        className="ml-auto font-sans text-label font-semibold text-red-primary hover:text-red-press"
      >
        Review →
      </button>
    </div>
  )
}
