import React from 'react'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import { DownloadHistory } from '../../components/DownloadHistory'

/**
 * DownloadHistory Component Tests (US-011: Download History View)
 *
 * Verifies:
 * - Loading, empty, error, and populated states
 * - Channel and status filters trigger refetches with correct query params
 * - Pagination controls and range display
 * - Status badges and error messages for failed downloads
 */

const mockDownloads = [
  {
    id: 1,
    channel_id: 1,
    channel_name: 'Channel A',
    video_id: 'abc12345678',
    title: 'First Video',
    status: 'completed',
    file_size: 1048576,
    file_exists: true,
    deleted_at: null,
    created_at: '2026-06-01T10:00:00',
    completed_at: '2026-06-01T10:05:00',
  },
  {
    id: 2,
    channel_id: 2,
    channel_name: 'Channel B',
    video_id: 'def12345678',
    title: 'Second Video',
    status: 'failed',
    error_message: 'Network error during download',
    file_exists: false,
    deleted_at: null,
    created_at: '2026-06-02T11:00:00',
    completed_at: null,
  },
]

const mockChannels = [
  { id: 1, name: 'Channel A' },
  { id: 2, name: 'Channel B' },
]

function mockFetchImplementation(downloads: object[] = mockDownloads, total = downloads.length) {
  return (url: string, options?: RequestInit) => {
    if (url.startsWith('/api/v1/channels')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ channels: mockChannels, total: 2, enabled: 2 }),
      })
    }
    if (url.includes('/retry') && options?.method === 'POST') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true, error_message: null, download: {} }),
      })
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ downloads, total }),
    })
  }
}

describe('DownloadHistory Component', () => {
  beforeEach(() => {
    global.fetch = jest.fn(mockFetchImplementation()) as jest.Mock
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders downloads with channel names, sizes, and status badges', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('First Video')).toBeInTheDocument()
    })

    expect(screen.getByText('Second Video')).toBeInTheDocument()
    expect(screen.getByText('1.0 MB')).toBeInTheDocument()

    // Channel names and status labels also appear in the filter dropdowns,
    // so scope these assertions to the table rows
    const table = screen.getByRole('table')
    const { getAllByText } = within(table)
    expect(getAllByText('Channel A').length).toBe(1)
    expect(getAllByText('Completed').length).toBe(1)
    expect(getAllByText('Failed').length).toBe(1)
  })

  it('shows "Cleaned up" badge for completed downloads whose file was removed', async () => {
    const cleanedUpDownload = {
      ...mockDownloads[0],
      id: 3,
      video_id: 'ghi12345678',
      title: 'Cleaned Up Video',
      file_exists: false,
      deleted_at: '2026-06-03T09:00:00',
    }
    global.fetch = jest.fn(mockFetchImplementation([cleanedUpDownload], 1)) as jest.Mock

    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Cleaned up')).toBeInTheDocument()
    })
  })

  it('shows error message for failed downloads', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Network error during download')).toBeInTheDocument()
    })
  })

  it('shows a Retry button only on failed downloads and triggers the retry', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Second Video')).toBeInTheDocument()
    })

    // Only the failed download (id=2) gets a Retry button
    const retryButtons = screen.getAllByRole('button', { name: /retry/i })
    expect(retryButtons).toHaveLength(1)

    fireEvent.click(retryButtons[0])

    await waitFor(() => {
      const retryCall = (global.fetch as jest.Mock).mock.calls.find(
        (call) => String(call[0]).includes('/retry')
      )
      expect(retryCall).toBeDefined()
      expect(retryCall[0]).toBe('/api/v1/downloads/2/retry')
      expect(retryCall[1]?.method).toBe('POST')
    })
  })

  it('surfaces an error when the retry fails again', async () => {
    global.fetch = jest.fn((url: string, options?: RequestInit) => {
      if (url.startsWith('/api/v1/channels')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ channels: mockChannels, total: 2, enabled: 2 }),
        })
      }
      if (url.includes('/retry') && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: false, error_message: 'Still unavailable', download: {} }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ downloads: mockDownloads, total: 2 }),
      })
    }) as jest.Mock

    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Second Video')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(screen.getByText(/Retry of "Second Video" failed: Still unavailable/)).toBeInTheDocument()
    })
  })

  it('shows empty state when there are no downloads', async () => {
    global.fetch = jest.fn(mockFetchImplementation([], 0)) as jest.Mock

    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('No downloads found')).toBeInTheDocument()
    })
  })

  it('shows an error message when the API request fails', async () => {
    global.fetch = jest.fn((url: string) => {
      if (url.startsWith('/api/v1/channels')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0, enabled: 0 }),
        })
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: 'Backend unavailable' }),
      })
    }) as jest.Mock

    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Backend unavailable')).toBeInTheDocument()
    })
  })

  it('refetches with status filter when status is selected', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('First Video')).toBeInTheDocument()
    })

    const statusSelect = screen.getByLabelText('Status')
    fireEvent.change(statusSelect, { target: { value: 'failed' } })

    await waitFor(() => {
      const calls = (global.fetch as jest.Mock).mock.calls.map((call) => call[0])
      expect(calls.some((url: string) => url.includes('status=failed'))).toBe(true)
    })
  })

  it('refetches with channel filter when a channel is selected', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('First Video')).toBeInTheDocument()
    })

    const channelSelect = screen.getByLabelText('Channel')
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Channel A' })).toBeInTheDocument()
    })
    fireEvent.change(channelSelect, { target: { value: '1' } })

    await waitFor(() => {
      const calls = (global.fetch as jest.Mock).mock.calls.map((call) => call[0])
      expect(calls.some((url: string) => url.includes('channel_id=1'))).toBe(true)
    })
  })

  it('shows pagination range and disables Previous on first page', async () => {
    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Showing 1–2 of 2')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('enables Next and paginates when there are more results', async () => {
    // total=75 with only 2 mock rows is intentional: pagination is driven by
    // the API's total, not the row count, so we don't need 50 fixture rows
    global.fetch = jest.fn(mockFetchImplementation(mockDownloads, 75)) as jest.Mock

    render(<DownloadHistory />)

    await waitFor(() => {
      expect(screen.getByText('Showing 1–50 of 75')).toBeInTheDocument()
    })

    const nextButton = screen.getByRole('button', { name: /next/i })
    expect(nextButton).not.toBeDisabled()
    fireEvent.click(nextButton)

    await waitFor(() => {
      const calls = (global.fetch as jest.Mock).mock.calls.map((call) => call[0])
      expect(calls.some((url: string) => url.includes('offset=50'))).toBe(true)
    })
  })
})
