import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Settings } from '../../components/Settings'

/**
 * Settings Tests — focused on the newer sections:
 * - Default Video Quality (US-015)
 * - YouTube cookies health display
 * - Failure notification configuration (Apprise)
 *
 * URL-dispatched fetch mocking covers the many independent fetches the
 * settings page performs on mount.
 */

const jsonResponse = (body: unknown, ok = true) => ({ ok, json: () => Promise.resolve(body) })

let cookieStatusResponse: object
let notificationsResponse: object

function installFetchMock() {
  ;(global.fetch as jest.Mock).mockImplementation((url: string, options?: RequestInit) => {
    if (url.startsWith('/api/v1/settings/default-video-limit')) {
      return Promise.resolve(jsonResponse({
        limit: 10,
        description: 'Default limit',
        updated_at: '2026-01-01T00:00:00',
      }))
    }
    if (url.startsWith('/api/v1/settings/default-quality')) {
      if (options?.method === 'PUT') {
        return Promise.resolve(jsonResponse({
          quality: JSON.parse(String(options.body)).quality,
          description: 'Default quality',
          updated_at: '2026-01-01T00:00:00',
        }))
      }
      return Promise.resolve(jsonResponse({
        quality: '1080p',
        description: 'Default quality',
        updated_at: '2026-01-01T00:00:00',
      }))
    }
    if (url.startsWith('/api/v1/settings/cookies-status')) {
      return Promise.resolve(jsonResponse(cookieStatusResponse))
    }
    if (url.startsWith('/api/v1/settings/notifications/test')) {
      return Promise.resolve(jsonResponse({ message: 'Test notification sent' }))
    }
    if (url.startsWith('/api/v1/settings/notifications')) {
      if (options?.method === 'PUT') {
        const body = JSON.parse(String(options.body))
        return Promise.resolve(jsonResponse({ url: body.url, enabled: !!body.url }))
      }
      return Promise.resolve(jsonResponse(notificationsResponse))
    }
    if (url.startsWith('/api/v1/settings/nfo')) {
      return Promise.resolve(jsonResponse({ enabled: true, overwrite_existing: false }))
    }
    if (url.startsWith('/api/v1/scheduler/status')) {
      return Promise.resolve(jsonResponse({
        scheduler_running: false,
        scheduler_enabled: true,
        cron_schedule: '0 0 * * *',
        next_run: null,
        last_run: null,
        download_job_active: true,
        total_jobs: 1,
      }))
    }
    if (url.startsWith('/api/v1/channels')) {
      return Promise.resolve(jsonResponse({ channels: [], total: 0, enabled: 0 }))
    }
    return Promise.resolve(jsonResponse({}))
  })
}

describe('Settings Component - quality, cookies, notifications', () => {
  beforeEach(() => {
    global.fetch = jest.fn() as jest.Mock
    cookieStatusResponse = { present: true, age_days: 3, stale: false }
    notificationsResponse = { url: '', enabled: false }
    installFetchMock()
  })

  afterEach(() => {
    ;(global.fetch as jest.Mock).mockReset()
  })

  it('loads and saves the default video quality (US-015)', async () => {
    render(<Settings />)

    await waitFor(() => {
      expect(screen.getByLabelText('Default Video Quality')).toHaveValue('1080p')
    })

    fireEvent.change(screen.getByLabelText('Default Video Quality'), { target: { value: '720p' } })
    const saveButtons = screen.getAllByRole('button', { name: /^save$/i })
    // Second Save button belongs to the quality section (first is limit)
    fireEvent.click(saveButtons[1])

    await waitFor(() => {
      const putCall = (global.fetch as jest.Mock).mock.calls.find(
        (c) => String(c[0]).includes('default-quality') && c[1]?.method === 'PUT'
      )
      expect(putCall).toBeDefined()
      expect(JSON.parse(putCall[1].body)).toEqual({ quality: '720p' })
    })
  })

  it('shows healthy cookie status', async () => {
    render(<Settings />)

    await waitFor(() => {
      expect(screen.getByText(/Cookies file present \(3 days old\)/)).toBeInTheDocument()
    })
  })

  it('warns when cookies are stale or missing', async () => {
    cookieStatusResponse = { present: true, age_days: 45, stale: true }

    render(<Settings />)

    await waitFor(() => {
      expect(screen.getByText(/45 days old — YouTube sessions typically expire/)).toBeInTheDocument()
    })
  })

  it('saves a notification URL and enables the Test button', async () => {
    render(<Settings />)

    await waitFor(() => {
      expect(screen.getByLabelText(/Failure Notifications/)).toBeInTheDocument()
    })

    // Test button disabled until a URL is saved
    expect(screen.getByRole('button', { name: /^test$/i })).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/Failure Notifications/), {
      target: { value: 'ntfy://ntfy.sh/my-topic' },
    })
    // Buttons named exactly "Save": limit, quality, notifications (in order)
    const saveButtons = screen.getAllByRole('button', { name: /^save$/i })
    fireEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => {
      const putCall = (global.fetch as jest.Mock).mock.calls.find(
        (c) => String(c[0]) === '/api/v1/settings/notifications' && c[1]?.method === 'PUT'
      )
      expect(putCall).toBeDefined()
      expect(JSON.parse(putCall[1].body)).toEqual({ url: 'ntfy://ntfy.sh/my-topic' })
    })

    await waitFor(() => {
      expect(screen.getByText('Notifications enabled')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /^test$/i })).not.toBeDisabled()
    })
  })
})
