import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WritingVolumeTrends } from './writing-volume-trends'
import type {
  CategoryImprovement,
  FlagVolumePoint,
} from '@/lib/patterns-contract'

function volumePoint(over: Partial<FlagVolumePoint> = {}): FlagVolumePoint {
  return {
    period: '2026-01',
    document_count: 2,
    flag_count: 4,
    flags_per_document: 2.0,
    ...over,
  }
}

function improvement(
  over: Partial<CategoryImprovement> = {},
): CategoryImprovement {
  return {
    category: 'gender',
    first_period: '2026-01',
    last_period: '2026-06',
    first_rate: 1.0,
    last_rate: 0.0,
    reduction: 1.0,
    ...over,
  }
}

describe('WritingVolumeTrends', () => {
  it('renders the flags-over-time chart with month labels and a first-to-last caption', () => {
    render(
      <WritingVolumeTrends
        flagVolume={[
          volumePoint({ period: '2026-01', flags_per_document: 2.0 }),
          volumePoint({ period: '2026-06', flags_per_document: 0.7 }),
        ]}
        improvements={[]}
      />,
    )

    expect(screen.getByText('Bias flags over time')).toBeInTheDocument()
    expect(screen.getByText('Jan')).toBeInTheDocument()
    expect(screen.getByText('Jun')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Your average flags per document went from 2.0 in Jan to 0.7 in Jun.',
      ),
    ).toBeInTheDocument()
  })

  it('omits the delta caption when there is only one period', () => {
    render(
      <WritingVolumeTrends
        flagVolume={[volumePoint({ period: '2026-03' })]}
        improvements={[]}
      />,
    )

    expect(screen.getByText('Mar')).toBeInTheDocument()
    expect(
      screen.queryByText(/Your average flags per document went from/),
    ).not.toBeInTheDocument()
  })

  it('shows a neutral empty state when there is no volume history', () => {
    render(
      <WritingVolumeTrends flagVolume={[]} improvements={[improvement()]} />,
    )

    expect(screen.getByText('Not enough history yet')).toBeInTheDocument()
  })

  it('renders the improvement chart with a bar per improved category', () => {
    render(
      <WritingVolumeTrends
        flagVolume={[]}
        improvements={[
          improvement({ category: 'gender' }),
          improvement({
            category: 'age',
            first_rate: 2.0,
            last_rate: 1.0,
            reduction: 1.0,
          }),
        ]}
      />,
    )

    expect(screen.getByText("Where you've improved")).toBeInTheDocument()
    expect(screen.getByText('Gender')).toBeInTheDocument()
    expect(screen.getByText('Age')).toBeInTheDocument()
    expect(screen.queryByText('No category trends yet')).not.toBeInTheDocument()
  })

  it('shows a neutral empty state when no category has improved', () => {
    render(
      <WritingVolumeTrends flagVolume={[volumePoint()]} improvements={[]} />,
    )

    expect(screen.getByText('No category trends yet')).toBeInTheDocument()
  })
})
