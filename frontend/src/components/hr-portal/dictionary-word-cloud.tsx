// clsx, not the usual cn(): the size and colour tokens are both text-* utilities, and cn()'s
// tailwind-merge would treat them as one group and drop the colour. No className is merged in here.
import { clsx } from 'clsx'
import {
  GROWTH_CATEGORY_COLOR,
  GROWTH_CATEGORY_DOT,
  wordSizeClass,
} from '@/lib/growth-format'
import type { GrowthBiasCategory, PendingAddition } from '@/lib/growth-contract'

interface DictionaryWordCloudProps {
  additions: PendingAddition[]
  onReview: (addition: PendingAddition) => void
}

const CATEGORY_LABELS: Record<GrowthBiasCategory, string> = {
  gender: 'Gender',
  age: 'Age',
  race: 'Race',
  nationality: 'Nationality',
  religion: 'Religion',
  disability: 'Disability',
  family_status: 'Family status',
}

/** The pending dictionary additions as a word cloud (#72): each phrase sized by how often the
 *  Contextual Pass flagged it and coloured by its proposed bias category. Clicking a word opens
 *  the same review the queue list does. Additions arrive pre-sorted; the max scales the sizes. */
export function DictionaryWordCloud({
  additions,
  onReview,
}: Readonly<DictionaryWordCloudProps>) {
  const maxCount = additions.reduce(
    (max, addition) => Math.max(max, addition.flag_count),
    0,
  )
  const categories = [...new Set(additions.map((a) => a.proposed_category))]

  return (
    <div className="rounded-card bg-surface p-8 shadow-ring-card">
      <div className="flex flex-wrap items-baseline justify-center gap-x-6 gap-y-3">
        {additions.map((addition) => (
          <button
            key={addition.id}
            type="button"
            onClick={() => onReview(addition)}
            title={`${addition.phrase} — flagged ${addition.flag_count} time${
              addition.flag_count === 1 ? '' : 's'
            }`}
            className={clsx(
              'font-serif leading-none font-semibold transition-opacity hover:opacity-70',
              GROWTH_CATEGORY_COLOR[addition.proposed_category],
              wordSizeClass(addition.flag_count, maxCount),
              addition.status === 'deferred' && 'opacity-50',
            )}
          >
            {addition.phrase}
          </button>
        ))}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 border-t border-border pt-5 font-sans text-meta text-ink-faint">
        <span>Larger = flagged more often.</span>
        {categories.map((category) => (
          <span key={category} className="inline-flex items-center gap-1.5">
            <span
              className={clsx(
                'inline-block size-2 rounded-full',
                GROWTH_CATEGORY_DOT[category],
              )}
            />
            {CATEGORY_LABELS[category]}
          </span>
        ))}
      </div>
    </div>
  )
}
