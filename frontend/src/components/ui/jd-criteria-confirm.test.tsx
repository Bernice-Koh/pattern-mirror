import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import {
  confirmJdCriteria,
  draftJdCriteria,
  getJdCriteria,
  JdCriteriaError,
} from '@/lib/jd-criteria-client'
import { JdCriteriaConfirm } from './jd-criteria-confirm'

vi.mock('@/lib/jd-criteria-client', async () => {
  const actual = await vi.importActual<
    typeof import('@/lib/jd-criteria-client')
  >('@/lib/jd-criteria-client')
  return {
    ...actual,
    getJdCriteria: vi.fn(),
    draftJdCriteria: vi.fn(),
    confirmJdCriteria: vi.fn(),
  }
})

const getJdCriteriaMock = vi.mocked(getJdCriteria)
const draftJdCriteriaMock = vi.mocked(draftJdCriteria)
const confirmJdCriteriaMock = vi.mocked(confirmJdCriteria)

function renderModal(onConfirmed = vi.fn()) {
  render(
    <JdCriteriaConfirm
      open
      documentId="d1"
      content="job description text"
      onClose={vi.fn()}
      onConfirmed={onConfirmed}
    />,
  )
  return onConfirmed
}

describe('JdCriteriaConfirm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    confirmJdCriteriaMock.mockResolvedValue({ criteria: [] })
  })

  it('drafts criteria from the JD when none are confirmed yet, and confirms the edited set', async () => {
    getJdCriteriaMock.mockResolvedValue({ criteria: [] })
    draftJdCriteriaMock.mockResolvedValue({ criteria: ['Python proficiency'] })
    const onConfirmed = renderModal()

    const input = await screen.findByDisplayValue('Python proficiency')
    fireEvent.change(input, { target: { value: 'Strong Python' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & publish' }))

    await waitFor(() =>
      expect(confirmJdCriteriaMock).toHaveBeenCalledWith('d1', {
        criteria: ['Strong Python'],
      }),
    )
    expect(onConfirmed).toHaveBeenCalled()
  })

  it('pre-fills an already-confirmed set without drafting', async () => {
    getJdCriteriaMock.mockResolvedValue({ criteria: ['Existing criterion'] })
    renderModal()

    await screen.findByDisplayValue('Existing criterion')
    expect(draftJdCriteriaMock).not.toHaveBeenCalled()
  })

  it('still drafts when the existing-criteria read fails', async () => {
    getJdCriteriaMock.mockRejectedValue(new JdCriteriaError(404))
    draftJdCriteriaMock.mockResolvedValue({ criteria: ['Drafted anyway'] })
    renderModal()

    await screen.findByDisplayValue('Drafted anyway')
    expect(draftJdCriteriaMock).toHaveBeenCalledWith('d1', {
      content: 'job description text',
    })
  })

  it('falls back to manual entry when drafting fails', async () => {
    getJdCriteriaMock.mockResolvedValue({ criteria: [] })
    draftJdCriteriaMock.mockRejectedValue(new JdCriteriaError(503))
    renderModal()

    await screen.findByText(/couldn’t draft criteria/)
    fireEvent.change(screen.getByLabelText('Criterion'), {
      target: { value: 'Manual criterion' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & publish' }))

    await waitFor(() =>
      expect(confirmJdCriteriaMock).toHaveBeenCalledWith('d1', {
        criteria: ['Manual criterion'],
      }),
    )
  })

  it('drops blank rows from the confirmed set', async () => {
    getJdCriteriaMock.mockResolvedValue({ criteria: ['Kept'] })
    renderModal()

    await screen.findByDisplayValue('Kept')
    fireEvent.click(screen.getByRole('button', { name: 'Add criterion' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm & publish' }))

    await waitFor(() =>
      expect(confirmJdCriteriaMock).toHaveBeenCalledWith('d1', {
        criteria: ['Kept'],
      }),
    )
  })
})
