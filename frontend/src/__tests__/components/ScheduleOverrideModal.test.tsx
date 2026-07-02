import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ScheduleOverrideModal } from '../../components/ScheduleOverrideModal'

/**
 * ScheduleOverrideModal Tests (US-016: Schedule Configuration)
 *
 * Verifies:
 * - Live validation feedback (valid + invalid expressions)
 * - Save sends PUT with the cron expression and reports back via onSaved
 * - "Use global schedule" clears the override (PUT null)
 * - Save button gating on validation state
 */

function mockFetch({ valid = true, putOk = true } = {}) {
  return jest.fn((url: string, options?: RequestInit) => {
    if (url.startsWith('/api/v1/scheduler/validate')) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            valid
              ? { valid: true, error: null, next_run: '2026-06-12T06:00:00+00:00', human_readable: 'Every 6 hours' }
              : { valid: false, error: 'Invalid cron expression: bad field', human_readable: 'Invalid expression' }
          ),
      })
    }
    if (options?.method === 'PUT') {
      return Promise.resolve({
        ok: putOk,
        json: () => Promise.resolve(putOk ? {} : { detail: 'Invalid schedule_override: rejected' }),
      })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  })
}

describe('ScheduleOverrideModal Component', () => {
  const onClose = jest.fn()
  const onSaved = jest.fn()

  beforeEach(() => {
    jest.clearAllMocks()
    global.fetch = mockFetch() as jest.Mock
  })

  it('renders channel name and schedule presets', () => {
    render(
      <ScheduleOverrideModal
        channelId={1}
        channelName="Mrs Rachel"
        currentOverride={null}
        onClose={onClose}
        onSaved={onSaved}
      />
    )

    expect(screen.getByText('Mrs Rachel')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Every 6 hours' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Daily at midnight' })).toBeInTheDocument()
    // No override set yet, so clearing is disabled
    expect(screen.getByRole('button', { name: /use global schedule/i })).toBeDisabled()
  })

  it('validates the expression and saves it', async () => {
    render(
      <ScheduleOverrideModal
        channelId={7}
        channelName="Test"
        currentOverride={null}
        onClose={onClose}
        onSaved={onSaved}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Every 6 hours' }))

    // Debounced validation runs and shows the description
    await waitFor(() => {
      expect(screen.getByText('Every 6 hours', { selector: 'p' })).toBeInTheDocument()
    })

    const saveButton = screen.getByRole('button', { name: /save schedule/i })
    expect(saveButton).not.toBeDisabled()
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith('0 */6 * * *')
      expect(onClose).toHaveBeenCalled()
    })

    const putCall = (global.fetch as jest.Mock).mock.calls.find((c) => c[1]?.method === 'PUT')
    expect(putCall[0]).toBe('/api/v1/channels/7')
    expect(JSON.parse(putCall[1].body)).toEqual({ schedule_override: '0 */6 * * *' })
  })

  it('shows the validation error and disables save for invalid expressions', async () => {
    global.fetch = mockFetch({ valid: false }) as jest.Mock

    render(
      <ScheduleOverrideModal
        channelId={7}
        channelName="Test"
        currentOverride={null}
        onClose={onClose}
        onSaved={onSaved}
      />
    )

    fireEvent.change(screen.getByLabelText(/cron expression/i), {
      target: { value: '99 99 * * *' },
    })

    await waitFor(() => {
      expect(screen.getByText('Invalid cron expression: bad field')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /save schedule/i })).toBeDisabled()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('clears the override via "Use global schedule"', async () => {
    render(
      <ScheduleOverrideModal
        channelId={7}
        channelName="Test"
        currentOverride="0 */2 * * *"
        onClose={onClose}
        onSaved={onSaved}
      />
    )

    const clearButton = screen.getByRole('button', { name: /use global schedule/i })
    expect(clearButton).not.toBeDisabled()
    fireEvent.click(clearButton)

    await waitFor(() => {
      expect(onSaved).toHaveBeenCalledWith(null)
    })

    const putCall = (global.fetch as jest.Mock).mock.calls.find((c) => c[1]?.method === 'PUT')
    expect(JSON.parse(putCall[1].body)).toEqual({ schedule_override: null })
  })

  it('surfaces a save error without closing the modal', async () => {
    global.fetch = mockFetch({ putOk: false }) as jest.Mock

    render(
      <ScheduleOverrideModal
        channelId={7}
        channelName="Test"
        currentOverride="0 */2 * * *"
        onClose={onClose}
        onSaved={onSaved}
      />
    )

    fireEvent.click(screen.getByRole('button', { name: /use global schedule/i }))

    await waitFor(() => {
      expect(screen.getByText('Invalid schedule_override: rejected')).toBeInTheDocument()
    })
    expect(onClose).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
  })
})
