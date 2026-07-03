import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AutosaveStatus } from './autosave-status'

describe('AutosaveStatus', () => {
  it('renders nothing while idle so the meta line stays quiet', () => {
    const { container } = render(<AutosaveStatus state="idle" />)

    expect(container).toBeEmptyDOMElement()
  })

  it('shows a saving indicator while saving', () => {
    render(<AutosaveStatus state="saving" />)

    expect(screen.getByText('Saving…')).toBeInTheDocument()
  })

  it('shows a saved confirmation once saved', () => {
    render(<AutosaveStatus state="saved" />)

    expect(screen.getByText('Saved')).toBeInTheDocument()
  })

  it('surfaces an error message when a save fails', () => {
    render(<AutosaveStatus state="error" />)

    expect(screen.getByText('Couldn’t save')).toBeInTheDocument()
  })
})
