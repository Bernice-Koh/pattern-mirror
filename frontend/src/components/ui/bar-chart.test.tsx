import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BarChart } from './bar-chart'

const DATA = [
  { label: 'Jan', value: 50 },
  { label: 'Feb', value: 100 },
]

describe('BarChart', () => {
  it('renders a labelled column per datum', () => {
    render(<BarChart data={DATA} />)
    expect(screen.getByText('Jan')).toBeInTheDocument()
    expect(screen.getByText('Feb')).toBeInTheDocument()
  })

  it('scales bar heights to the largest value', () => {
    const { container } = render(<BarChart data={DATA} />)
    const bars = container.querySelectorAll('[style*="--bar-height"]')
    expect(bars[0]).toHaveStyle({ '--bar-height': '50%' })
    expect(bars[1]).toHaveStyle({ '--bar-height': '100%' })
  })

  it('scales against a fixed max when given, keeping heights absolute', () => {
    const { container } = render(<BarChart data={DATA} max={200} />)
    const bars = container.querySelectorAll('[style*="--bar-height"]')
    expect(bars[0]).toHaveStyle({ '--bar-height': '25%' })
    expect(bars[1]).toHaveStyle({ '--bar-height': '50%' })
  })

  it('renders the caption when given', () => {
    render(<BarChart data={DATA} caption="Up since January." />)
    expect(screen.getByText('Up since January.')).toBeInTheDocument()
  })

  it('applies the requested bar colour', () => {
    const { container } = render(
      <BarChart data={DATA} barClassName="bg-green-positive" />,
    )
    expect(container.querySelector('[style*="--bar-height"]')).toHaveClass(
      'bg-green-positive',
    )
  })
})
