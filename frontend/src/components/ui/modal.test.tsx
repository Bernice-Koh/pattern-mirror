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
})
