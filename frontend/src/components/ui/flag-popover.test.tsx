import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FlagPopover } from './flag-popover'

describe('FlagPopover', () => {
  it('shows Apply only when there are suggestions', () => {
    render(
      <FlagPopover
        category="Race"
        source="AI pass"
        suggestions={['values alignment', 'team contribution']}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument()
  })

  it('hides Apply when there are no suggestions', () => {
    render(
      <FlagPopover
        category="Race"
        source="AI pass"
        onApply={vi.fn()}
        onDismiss={vi.fn()}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Apply' })).toBeNull()
  })

  it('selects a chip without applying, then applies it on Apply', () => {
    const onApply = vi.fn()
    render(
      <FlagPopover
        category="Race"
        source="AI pass"
        suggestions={['values alignment', 'team contribution']}
        onApply={onApply}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'team contribution' }))
    expect(onApply).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
    expect(onApply).toHaveBeenCalledWith('team contribution')
  })

  it('dismisses via the × button', () => {
    const onDismiss = vi.fn()
    render(
      <FlagPopover category="Race" source="AI pass" onDismiss={onDismiss} />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss flag' }))

    expect(onDismiss).toHaveBeenCalled()
  })
})
