/** Presentation helpers for the dictionary word cloud (#72): a bias-category colour and a
 *  frequency-driven word size. Kept apart from the effectiveness dashboard's category palette,
 *  which maps a different enum (patterns-contract BiasCategory, with `relevance` and no `religion`). */

import type { GrowthBiasCategory } from '@/lib/growth-contract'

/** WFA characteristic text colour per growth category, in lockstep with the manager surfaces. */
export const GROWTH_CATEGORY_COLOR: Record<GrowthBiasCategory, string> = {
  gender: 'text-wfa-sex',
  age: 'text-wfa-age',
  race: 'text-wfa-race',
  nationality: 'text-wfa-nationality',
  religion: 'text-wfa-religion',
  disability: 'text-wfa-disability',
  family_status: 'text-wfa-caregiving',
}

/** The same palette as background, for the legend swatches — written out so Tailwind's scanner
 *  finds each class literally rather than a name built at runtime. */
export const GROWTH_CATEGORY_DOT: Record<GrowthBiasCategory, string> = {
  gender: 'bg-wfa-sex',
  age: 'bg-wfa-age',
  race: 'bg-wfa-race',
  nationality: 'bg-wfa-nationality',
  religion: 'bg-wfa-religion',
  disability: 'bg-wfa-disability',
  family_status: 'bg-wfa-caregiving',
}

/** Type-scale steps a word grows through as it is flagged more often, smallest to largest. */
const SIZE_STEPS = [
  'text-body-sm',
  'text-subheading',
  'text-title',
  'text-display',
] as const

/** The size class for a word flagged `count` times, scaled against the busiest word (`max`).
 *  Discrete steps rather than a raw font size keep the cloud on the type scale and testable. */
export function wordSizeClass(count: number, max: number): string {
  if (max <= 0) return SIZE_STEPS[0]
  const ratio = count / max
  const step = Math.ceil(ratio * SIZE_STEPS.length) - 1
  return SIZE_STEPS[Math.min(Math.max(step, 0), SIZE_STEPS.length - 1)]
}
