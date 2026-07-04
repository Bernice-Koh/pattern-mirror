import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { InsightCallout } from './insight-callout'

describe('InsightCallout', () => {
  it('renders the eyebrow, lead, and takeaway', () => {
    render(
      <InsightCallout eyebrow="What peers say" lead="Peers evidence delivery.">
        The evidence is in your peers’ words.
      </InsightCallout>,
    )

    expect(screen.getByText('What peers say')).toBeInTheDocument()
    expect(screen.getByText('Peers evidence delivery.')).toBeInTheDocument()
    expect(
      screen.getByText('The evidence is in your peers’ words.'),
    ).toBeInTheDocument()
  })

  it('renders the takeaway without an eyebrow or lead', () => {
    render(<InsightCallout>Just the takeaway.</InsightCallout>)

    expect(screen.getByText('Just the takeaway.')).toBeInTheDocument()
    expect(screen.queryByText('What peers say')).not.toBeInTheDocument()
  })
})
