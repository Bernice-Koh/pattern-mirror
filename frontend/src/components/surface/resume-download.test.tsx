import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ResumeDownload } from './resume-download'
import { downloadResume } from '@/lib/resume-client'

vi.mock('@/lib/resume-client', () => ({ downloadResume: vi.fn() }))

describe('ResumeDownload', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when there is no subject', () => {
    const { container } = render(
      <ResumeDownload subjectId={null} subjectName={null} />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('downloads the resume with a name-based fallback filename on click', async () => {
    vi.mocked(downloadResume).mockResolvedValue()
    render(<ResumeDownload subjectId="subj-1" subjectName="Ada Lovelace" />)

    fireEvent.click(screen.getByRole('button', { name: 'Download résumé' }))

    await waitFor(() =>
      expect(downloadResume).toHaveBeenCalledWith(
        'subj-1',
        'Ada Lovelace-resume.pdf',
      ),
    )
  })

  it('shows a retry label when the download fails', async () => {
    vi.mocked(downloadResume).mockRejectedValue(new Error('boom'))
    render(<ResumeDownload subjectId="subj-1" subjectName="Ada Lovelace" />)

    fireEvent.click(screen.getByRole('button', { name: 'Download résumé' }))

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Retry download' }),
      ).toBeInTheDocument(),
    )
  })
})
