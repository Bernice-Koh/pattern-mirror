import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CoverageList } from './coverage-list'

describe('CoverageList', () => {
  it('renders the title and summary pill', () => {
    render(
      <CoverageList
        title="Coverage"
        summary="3 of 4 not addressed"
        items={[]}
      />,
    )

    expect(
      screen.getByRole('heading', { name: 'Coverage' }),
    ).toBeInTheDocument()
    expect(screen.getByText('3 of 4 not addressed')).toBeInTheDocument()
  })

  it('marks addressed and unaddressed criteria with their default status', () => {
    render(
      <CoverageList
        items={[
          { label: 'Strong SQL', addressed: true },
          { label: '5+ years Python', addressed: false },
        ]}
      />,
    )

    expect(screen.getByText('Strong SQL')).toBeInTheDocument()
    expect(screen.getByText('addressed')).toBeInTheDocument()
    expect(screen.getByText('not addressed')).toBeInTheDocument()
  })

  it('uses a custom statusLabel when provided', () => {
    render(
      <CoverageList
        items={[
          {
            label: 'Mentorship',
            addressed: false,
            statusLabel: 'not yet checked',
          },
        ]}
      />,
    )

    expect(screen.getByText('not yet checked')).toBeInTheDocument()
  })

  it('renders the optional corroboration pill alongside the status', () => {
    render(
      <CoverageList
        items={[
          {
            label: 'Owns delivery',
            addressed: false,
            statusLabel: 'not evidenced',
            corroboration: { corroborated: true, label: 'peers agree' },
          },
        ]}
      />,
    )

    expect(screen.getByText('peers agree')).toBeInTheDocument()
    expect(screen.getByText('not evidenced')).toBeInTheDocument()
  })
})
