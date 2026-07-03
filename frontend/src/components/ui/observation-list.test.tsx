import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ObservationList } from './observation-list'

describe('ObservationList', () => {
  it('shows the count and a row per observation', () => {
    render(
      <ObservationList
        items={[
          {
            id: 'a',
            phrase: 'nervous',
            category: 'Gender-coded',
            sourceStage: 'contextual',
          },
          {
            id: 'b',
            phrase: 'culture fit',
            category: 'Race',
            sourceStage: 'dictionary',
          },
        ]}
      />,
    )

    expect(screen.getByText('2 found')).toBeInTheDocument()
    expect(screen.getByText('nervous')).toBeInTheDocument()
    expect(screen.getByText('culture fit')).toBeInTheDocument()
  })

  it('renders an empty state when there are no observations', () => {
    render(<ObservationList items={[]} />)

    expect(screen.getByText('0 found')).toBeInTheDocument()
    expect(screen.getByText(/nothing flagged/i)).toBeInTheDocument()
  })
})
