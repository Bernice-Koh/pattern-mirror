import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FlagCard } from './flag-card'

describe('FlagCard', () => {
  it('shows Apply only when there are suggestions', () => {
    render(<FlagCard suggestions={['assertive', 'driven']} />)
    expect(screen.getByRole('button', { name: 'Apply' })).toBeInTheDocument()
  })

  it('hides Apply when there are no suggestions', () => {
    render(<FlagCard suggestions={[]} />)
    expect(screen.queryByRole('button', { name: 'Apply' })).toBeNull()
    expect(
      screen.getByRole('button', { name: 'Dismiss flag' }),
    ).toBeInTheDocument()
  })

  it('applies the pre-selected first suggestion when Apply is clicked', () => {
    const onApply = vi.fn()
    render(<FlagCard suggestions={['assertive', 'driven']} onApply={onApply} />)

    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(onApply).toHaveBeenCalledWith('assertive')
  })

  it('does not apply when a suggestion chip is clicked, only selects it', () => {
    const onApply = vi.fn()
    render(<FlagCard suggestions={['assertive', 'driven']} onApply={onApply} />)

    fireEvent.click(screen.getByRole('button', { name: 'driven' }))

    expect(onApply).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'driven' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('applies the chosen suggestion after selecting it then clicking Apply', () => {
    const onApply = vi.fn()
    render(<FlagCard suggestions={['assertive', 'driven']} onApply={onApply} />)

    fireEvent.click(screen.getByRole('button', { name: 'driven' }))
    fireEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(onApply).toHaveBeenCalledWith('driven')
  })

  it('offers Undo instead of actions once dismissed', () => {
    render(<FlagCard suggestions={['assertive']} dismissed />)
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apply' })).toBeNull()
  })
})
