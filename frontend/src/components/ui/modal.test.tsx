import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Modal } from './modal'

describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onClose={() => {}} title="Review">
        <p>Body</p>
      </Modal>,
    )
    expect(screen.queryByText('Body')).toBeNull()
  })

  it('renders children in a labelled dialog when open', () => {
    render(
      <Modal open onClose={() => {}} title="Review rockstar">
        <p>Body</p>
      </Modal>,
    )
    expect(screen.getByRole('dialog')).toHaveAttribute(
      'aria-label',
      'Review rockstar',
    )
    expect(screen.getByText('Body')).toBeInTheDocument()
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="Review">
        <p>Body</p>
      </Modal>,
    )
    fireEvent.keyDown(document.body, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes when the backdrop is clicked, but not the panel', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="Review">
        <p>Body</p>
      </Modal>,
    )
    const panel = screen.getByRole('dialog')
    fireEvent.mouseDown(panel)
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.mouseDown(panel.parentElement as HTMLElement)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('traps Tab from the last focusable back to the first', () => {
    render(
      <Modal open onClose={() => {}} title="Review">
        <button type="button">First</button>
        <button type="button">Last</button>
      </Modal>,
    )
    const first = screen.getByRole('button', { name: 'First' })
    const last = screen.getByRole('button', { name: 'Last' })

    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
  })

  it('traps Shift+Tab from the first focusable to the last', () => {
    render(
      <Modal open onClose={() => {}} title="Review">
        <button type="button">First</button>
        <button type="button">Last</button>
      </Modal>,
    )
    const first = screen.getByRole('button', { name: 'First' })
    const last = screen.getByRole('button', { name: 'Last' })

    first.focus()
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('leaves focus alone for a Tab in the middle of the order', () => {
    render(
      <Modal open onClose={() => {}} title="Review">
        <button type="button">First</button>
        <button type="button">Last</button>
      </Modal>,
    )
    const first = screen.getByRole('button', { name: 'First' })

    first.focus()
    fireEvent.keyDown(first, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
  })

  it('ignores Tab when there is nothing focusable', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="Review">
        <p>Body</p>
      </Modal>,
    )
    fireEvent.keyDown(document.body, { key: 'Tab' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('restores focus to the trigger when it closes', () => {
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    trigger.focus()

    const { rerender } = render(
      <Modal open onClose={() => {}} title="Review">
        <button type="button">Inside</button>
      </Modal>,
    )
    rerender(
      <Modal open={false} onClose={() => {}} title="Review">
        <button type="button">Inside</button>
      </Modal>,
    )

    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })
})
