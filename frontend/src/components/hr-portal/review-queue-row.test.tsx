import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ReviewQueueRow } from './review-queue-row'

describe('ReviewQueueRow', () => {
  it('shows the rank, phrase, and proposed category', () => {
    render(
      <ReviewQueueRow
        rank={3}
        phrase="rockstar"
        category="family_status"
        onReview={() => {}}
      />,
    )
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('rockstar')).toBeInTheDocument()
    expect(screen.getByText('family status')).toBeInTheDocument()
  })

  it('marks a deferred phrase', () => {
    render(
      <ReviewQueueRow
        rank={1}
        phrase="guru"
        category="age"
        status="deferred"
        onReview={() => {}}
      />,
    )
    expect(screen.getByText('Deferred')).toBeInTheDocument()
  })

  it('calls onReview when the action is clicked', () => {
    const onReview = vi.fn()
    render(
      <ReviewQueueRow
        rank={1}
        phrase="guru"
        category="age"
        onReview={onReview}
      />,
    )
    fireEvent.click(screen.getByText('Review →'))
    expect(onReview).toHaveBeenCalledOnce()
  })
})
