import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DictionaryWordCloud } from './dictionary-word-cloud'
import type { PendingAddition } from '@/lib/growth-contract'

function addition(overrides: Partial<PendingAddition> = {}): PendingAddition {
  return {
    id: 'a1',
    proposal_id: 'p1',
    phrase: 'rockstar',
    proposed_category: 'age',
    explanation: 'Youth-coded.',
    status: 'pending',
    created_at: '2026-06-01T00:00:00Z',
    decided_at: null,
    citation: null,
    flag_count: 1,
    ...overrides,
  }
}

describe('DictionaryWordCloud', () => {
  it('renders each pending phrase as a word', () => {
    render(
      <DictionaryWordCloud
        additions={[
          addition({ id: 'a1', phrase: 'rockstar' }),
          addition({ id: 'a2', phrase: 'cultural fit' }),
        ]}
        onReview={vi.fn()}
      />,
    )

    expect(screen.getByText('rockstar')).toBeInTheDocument()
    expect(screen.getByText('cultural fit')).toBeInTheDocument()
  })

  it('sizes the most-flagged word larger than the least-flagged', () => {
    render(
      <DictionaryWordCloud
        additions={[
          addition({ id: 'a1', phrase: 'common', flag_count: 10 }),
          addition({ id: 'a2', phrase: 'rare', flag_count: 1 }),
        ]}
        onReview={vi.fn()}
      />,
    )

    expect(screen.getByText('common').className).toContain('text-display')
    expect(screen.getByText('rare').className).toContain('text-body-sm')
  })

  it('colours a word by its bias category', () => {
    render(
      <DictionaryWordCloud
        additions={[
          addition({ phrase: 'aggressive', proposed_category: 'gender' }),
        ]}
        onReview={vi.fn()}
      />,
    )

    expect(screen.getByText('aggressive').className).toContain('text-wfa-sex')
  })

  it('opens the review when a word is clicked', () => {
    const onReview = vi.fn()
    const item = addition({ phrase: 'rockstar' })
    render(<DictionaryWordCloud additions={[item]} onReview={onReview} />)

    fireEvent.click(screen.getByText('rockstar'))

    expect(onReview).toHaveBeenCalledWith(item)
  })
})
