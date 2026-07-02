import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ActiveDownloads } from '../../components/ActiveDownloads'

/**
 * ActiveDownloads Tests (US-010: Active Download Progress)
 *
 * Verifies:
 * - Renders nothing when no downloads are active
 * - Renders progress bars with title, channel, percent, speed, and ETA
 * - Shows the processing state after the transfer completes
 */

const activeDownload = {
  video_id: 'vid123',
  channel_id: 1,
  channel_name: 'Test Channel',
  title: 'Big Video',
  status: 'downloading',
  percent: 42.5,
  downloaded_bytes: 425 * 1024 * 1024,
  total_bytes: 1000 * 1024 * 1024,
  speed: 5 * 1024 * 1024,
  eta_seconds: 115,
}

function mockActive(active: object[]) {
  global.fetch = jest.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ active, count: active.length }),
    })
  ) as jest.Mock
}

describe('ActiveDownloads Component', () => {
  afterEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  it('renders nothing when idle', async () => {
    mockActive([])

    const { container } = render(<ActiveDownloads />)

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/downloads/active')
    })
    expect(container.firstChild).toBeNull()
  })

  it('renders progress details for an active download', async () => {
    mockActive([activeDownload])

    render(<ActiveDownloads />)

    await waitFor(() => {
      expect(screen.getByText('Downloading (1)')).toBeInTheDocument()
    })

    expect(screen.getByText('Big Video')).toBeInTheDocument()
    expect(screen.getByText('43%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '42.5')
    // Channel, sizes, speed, and ETA are combined in the detail line
    expect(screen.getByText(/Test Channel/)).toBeInTheDocument()
    expect(screen.getByText(/425\.0 MB of 1000\.0 MB/)).toBeInTheDocument()
    expect(screen.getByText(/5\.0 MB\/s/)).toBeInTheDocument()
    expect(screen.getByText(/1m 55s left/)).toBeInTheDocument()
  })

  it('shows processing state when transfer is finished', async () => {
    mockActive([{ ...activeDownload, status: 'processing', percent: 100 }])

    render(<ActiveDownloads />)

    await waitFor(() => {
      expect(screen.getByText('Processing')).toBeInTheDocument()
    })
  })
})
