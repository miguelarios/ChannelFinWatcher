import React, { useState, useEffect } from 'react'
import { CalendarClockIcon, XIcon, CheckCircleIcon, AlertCircleIcon, Loader2Icon } from 'lucide-react'

/**
 * ScheduleOverrideModal - Set or clear a channel's custom download schedule
 *
 * Completes User Story 16 (Schedule Configuration): channels with a custom
 * cron schedule run on their own scheduler job instead of the global one.
 *
 * Features:
 * - Cron expression input with live (debounced) validation via the backend,
 *   showing a human-readable description and the next run time
 * - Common schedule presets for one-click selection
 * - "Use global schedule" clears the override
 * - Saves via PUT /api/v1/channels/{id} (which also syncs the scheduler job)
 */

interface ValidationResult {
  valid: boolean
  error?: string
  next_run?: string
  human_readable?: string
}

interface ScheduleOverrideModalProps {
  channelId: number
  channelName: string
  currentOverride?: string | null
  onClose: () => void
  onSaved: (scheduleOverride: string | null) => void
}

const PRESETS = [
  { label: 'Every 6 hours', expression: '0 */6 * * *' },
  { label: 'Every hour', expression: '0 * * * *' },
  { label: 'Daily at midnight', expression: '0 0 * * *' },
  { label: 'Weekly on Sunday', expression: '0 0 * * 0' },
]

const VALIDATE_DEBOUNCE_MS = 400

export function ScheduleOverrideModal({
  channelId,
  channelName,
  currentOverride,
  onClose,
  onSaved,
}: ScheduleOverrideModalProps) {
  const [expression, setExpression] = useState(currentOverride || '')
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [isValidating, setIsValidating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Debounced live validation against the backend
  useEffect(() => {
    if (!expression.trim()) {
      setValidation(null)
      return
    }

    setIsValidating(true)
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/v1/scheduler/validate?expression=${encodeURIComponent(expression.trim())}`
        )
        const data = await response.json()
        setValidation({
          valid: !!data.valid,
          error: data.error,
          next_run: data.next_run,
          human_readable: data.human_readable,
        })
      } catch {
        setValidation({ valid: false, error: 'Could not validate expression' })
      } finally {
        setIsValidating(false)
      }
    }, VALIDATE_DEBOUNCE_MS)

    return () => {
      clearTimeout(timer)
      setIsValidating(false)
    }
  }, [expression])

  const save = async (override: string | null) => {
    setIsSaving(true)
    setSaveError('')
    try {
      const response = await fetch(`/api/v1/channels/${channelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schedule_override: override }),
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to save schedule')
      }
      onSaved(override)
      onClose()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save schedule')
    } finally {
      setIsSaving(false)
    }
  }

  const trimmed = expression.trim()
  const canSave = trimmed !== '' && validation?.valid === true && !isValidating && !isSaving

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" role="dialog" aria-label="Custom schedule">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center">
            <CalendarClockIcon className="h-5 w-5 mr-2 text-red-600" />
            <h3 className="text-lg font-semibold text-gray-900">Custom Schedule</h3>
          </div>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600">
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          Set a cron schedule for <span className="font-medium">{channelName}</span>.
          With a custom schedule, this channel runs on its own timing instead of the
          global schedule.
        </p>

        {/* Presets */}
        <div className="flex flex-wrap gap-2 mb-3">
          {PRESETS.map((preset) => (
            <button
              key={preset.expression}
              onClick={() => setExpression(preset.expression)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                trimmed === preset.expression
                  ? 'bg-red-600 text-white border-red-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-red-400'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Cron input */}
        <label htmlFor="cron-expression" className="block text-sm font-medium text-gray-700 mb-1">
          Cron expression (minute hour day month weekday)
        </label>
        <input
          id="cron-expression"
          type="text"
          value={expression}
          onChange={(e) => setExpression(e.target.value)}
          placeholder="0 */6 * * *"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-red-500 focus:ring-red-500"
        />

        {/* Validation feedback */}
        <div className="min-h-[2.5rem] mt-2">
          {trimmed !== '' && (
            isValidating ? (
              <p className="flex items-center text-sm text-gray-500">
                <Loader2Icon className="h-4 w-4 mr-1.5 animate-spin" />
                Validating...
              </p>
            ) : validation?.valid ? (
              <div className="text-sm text-green-700">
                <p className="flex items-center font-medium">
                  <CheckCircleIcon className="h-4 w-4 mr-1.5" />
                  {validation.human_readable || 'Valid schedule'}
                </p>
                {validation.next_run && (
                  <p className="text-xs text-gray-500 ml-5.5 mt-0.5">
                    Next run: {new Date(validation.next_run).toLocaleString()}
                  </p>
                )}
              </div>
            ) : validation ? (
              <p className="flex items-center text-sm text-red-600">
                <AlertCircleIcon className="h-4 w-4 mr-1.5 flex-shrink-0" />
                {validation.error || 'Invalid cron expression'}
              </p>
            ) : null
          )}
        </div>

        {saveError && (
          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-700">{saveError}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
          <button
            onClick={() => save(null)}
            disabled={isSaving || !currentOverride}
            title={currentOverride ? 'Remove the custom schedule' : 'No custom schedule set'}
            className="text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 underline-offset-2 hover:underline"
          >
            Use global schedule
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={isSaving}
              className="px-3 py-2 rounded-md text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => save(trimmed)}
              disabled={!canSave}
              className="px-3 py-2 rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {isSaving ? 'Saving...' : 'Save schedule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
