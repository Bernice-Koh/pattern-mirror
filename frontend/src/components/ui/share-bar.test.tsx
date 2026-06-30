import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ShareBar } from './share-bar'

describe('ShareBar', () => {
  it('renders the label and the value as a rounded percentage', () => {
    render(<ShareBar label="Interview feedback" value={0.474} />)

    expect(screen.getByText('Interview feedback')).toBeInTheDocument()
    expect(screen.getByText('47%')).toBeInTheDocument()
  })

  it('rounds a zero value to 0%', () => {
    render(<ShareBar label="Job descriptions" value={0} />)

    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('shows a colour dot in the fill colour when showDot is set', () => {
    const { container } = render(
      <ShareBar label="Gender" value={0.38} color="bg-wfa-sex" showDot />,
    )

    expect(container.querySelector('.bg-wfa-sex')).toBeInTheDocument()
  })
})
