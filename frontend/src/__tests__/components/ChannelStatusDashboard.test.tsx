import React from 'react'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ChannelStatusDashboard } from '../../components/ChannelStatusDashboard'

/**
 * ChannelStatusDashboard Tests (US-009 status dashboard + US-012 storage monitoring)
 *
 * Verifies:
 * - Storage overview, totals, and channel cards render from API data
 * - Storage warning banner appears at >= 80% usage
 * - Health indicators (active / disabled / failed / never checked)
 * - Search filtering and empty states
 * - Enable/disable quick action calls PUT and refetches
 */

const GB = 1024 * 1024 * 1024

const baseDashboard = {
  disk: {
    total_bytes: 100 * GB,
    used_bytes: 50 * GB,
    free_bytes: 50 * GB,
    usage_percent: 50.0,
    warning: false,
  },
  totals: { channels: 3, enabled_channels: 2, videos: 12, storage_bytes: 9 * GB },
  channels: [
    {
      id: 1,
      name: 'Active Channel',
      url: 'https://youtube.com/@active',
      enabled: true,
      limit: 10,
      metadata_status: 'completed',
      video_count: 8,
      storage_bytes: 5 * GB,
      last_check: '2026-06-09T10:00:00',
      last_run_status: 'completed',
      last_run_date: '2026-06-09T10:00:00',
      last_run_error: null,
    },
    {
      id: 2,
      name: 'Failing Channel',
      url: 'https://youtube.com/@failing',
      enabled: true,
      limit: 5,
      metadata_status: 'completed',
      video_count: 4,
      storage_bytes: 4 * GB,
      last_check: '2026-06-09T08:00:00',
      last_run_status: 'failed',
      last_run_date: '2026-06-09T08:00:00',
      last_run_error: 'Network error during run',
    },
    {
      id: 3,
      name: 'Disabled Channel',
      url: 'https://youtube.com/@disabled',
      enabled: false,
      limit: 10,
      metadata_status: 'pending',
      video_count: 0,
      storage_bytes: 0,
      last_check: null,
      last_run_status: null,
      last_run_date: null,
      last_run_error: null,
    },
  ],
  generated_at: '2026-06-09T12:00:00',
}

const schedulerStatus = {
  scheduler_running: true,
  scheduler_enabled: true,
  cron_schedule: '0 */6 * * *',
  next_run: null,
  last_run: null,
  download_job_active: true,
  total_jobs: 1,
}

function mockFetchImplementation(dashboard = baseDashboard) {
  return (url: string, options?: RequestInit) => {
    if (url.startsWith('/api/v1/scheduler/status')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(schedulerStatus) })
    }
    if (url.startsWith('/api/v1/channels/') && options?.method === 'PUT') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(dashboard) })
  }
}

describe('ChannelStatusDashboard Component', () => {
  beforeEach(() => {
    global.fetch = jest.fn(mockFetchImplementation()) as jest.Mock
  })

  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('renders channel cards with video counts and storage', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Active Channel')).toBeInTheDocument()
    })

    expect(screen.getByText('8/10 videos')).toBeInTheDocument()
    expect(screen.getByText('5.0 GB')).toBeInTheDocument()
    expect(screen.getByText('Failing Channel')).toBeInTheDocument()
    expect(screen.getByText('Disabled Channel')).toBeInTheDocument()
  })

  it('shows health indicators for each channel state', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument()
    })

    expect(screen.getByText('Last run failed')).toBeInTheDocument()
    expect(screen.getByText('Disabled')).toBeInTheDocument()
    expect(screen.getByText('Network error during run')).toBeInTheDocument()
  })

  it('renders the storage overview with capacity', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText(/50\.0 GB of 100\.0 GB used/)).toBeInTheDocument()
    })

    // No warning banner below the 80% threshold
    expect(screen.queryByText(/Storage is .*% full/)).not.toBeInTheDocument()
  })

  it('shows warning banner when storage is at or above 80%', async () => {
    const warningDashboard = {
      ...baseDashboard,
      disk: {
        total_bytes: 100 * GB,
        used_bytes: 85 * GB,
        free_bytes: 15 * GB,
        usage_percent: 85.0,
        warning: true,
      },
    }
    global.fetch = jest.fn(mockFetchImplementation(warningDashboard)) as jest.Mock

    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Storage is 85% full')).toBeInTheDocument()
    })
  })

  it('renders library totals', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Channels (2 enabled)')).toBeInTheDocument()
    })

    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('9.0 GB')).toBeInTheDocument()
  })

  it('filters channels by search query', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Active Channel')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Search channels'), {
      target: { value: 'failing' },
    })

    expect(screen.getByText('Failing Channel')).toBeInTheDocument()
    expect(screen.queryByText('Active Channel')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search channels'), {
      target: { value: 'zzz-no-match' },
    })
    expect(screen.getByText('No channels match your search.')).toBeInTheDocument()
  })

  it('shows empty state with add-channel CTA when there are no channels', async () => {
    const emptyDashboard = {
      ...baseDashboard,
      totals: { channels: 0, enabled_channels: 0, videos: 0, storage_bytes: 0 },
      channels: [],
    }
    global.fetch = jest.fn(mockFetchImplementation(emptyDashboard)) as jest.Mock
    const onNavigateToChannels = jest.fn()

    render(<ChannelStatusDashboard onNavigateToChannels={onNavigateToChannels} />)

    await waitFor(() => {
      expect(screen.getByText('No channels yet')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /add channel/i }))
    expect(onNavigateToChannels).toHaveBeenCalledTimes(1)
  })

  it('toggles channel enabled state via quick action', async () => {
    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Active Channel')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByTitle('Disable monitoring')[0])

    await waitFor(() => {
      const putCall = (global.fetch as jest.Mock).mock.calls.find(
        (call) => call[1]?.method === 'PUT'
      )
      expect(putCall).toBeDefined()
      expect(putCall[0]).toBe('/api/v1/channels/1')
      expect(JSON.parse(putCall[1].body)).toEqual({ enabled: false })
    })
  })

  it('shows an error message when the dashboard request fails', async () => {
    global.fetch = jest.fn((url: string) => {
      if (url.startsWith('/api/v1/scheduler/status')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(schedulerStatus) })
      }
      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ detail: 'Backend unavailable' }),
      })
    }) as jest.Mock

    render(<ChannelStatusDashboard />)

    await waitFor(() => {
      expect(screen.getByText('Backend unavailable')).toBeInTheDocument()
    })
  })
})
