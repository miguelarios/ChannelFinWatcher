import React, { useState, useEffect, useCallback } from 'react'
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle, Info, Clock, Calendar } from 'lucide-react'

/**
 * Interface for the default video limit settings response from API.
 *
 * This matches the DefaultVideoLimitResponse schema from the backend
 * and ensures type safety in the frontend component.
 */
interface DefaultVideoLimitSettings {
  limit: number
  description: string
  updated_at: string
}

/**
 * Interface for scheduler status response from API (Story 007).
 *
 * This matches the SchedulerStatusResponse schema from the backend
 * and provides type safety for scheduler state management.
 */
interface SchedulerStatus {
  scheduler_running: boolean
  scheduler_enabled: boolean
  cron_schedule: string | null
  next_run: string | null
  last_run: string | null
  download_job_active: boolean
  total_jobs: number
}

/**
 * Interface for cron validation response (Story 007).
 *
 * Used for real-time validation feedback as user types cron expression.
 */
interface CronValidationResult {
  valid: boolean
  error: string | null
  next_run: string | null
  next_5_runs: string[]
  time_until_next: string | null
  human_readable: string
}

/**
 * Settings Component for User Story 3 & Story 007.
 *
 * This component provides a user interface for configuring:
 * 1. Global default video limit (Story 3)
 * 2. Cron scheduler for automatic downloads (Story 007)
 *
 * Architecture Decisions:
 * - Real-time validation with immediate feedback
 * - Optimistic UI updates (show changes before server confirmation)
 * - Graceful error handling with user-friendly messages
 * - Auto-clearing success messages to reduce UI clutter
 * - Loading states for better perceived performance
 * - Debounced validation (500ms) to reduce API calls
 *
 * UX Patterns:
 * - Disabled save button when no changes or invalid values
 * - Change detection to prevent unnecessary API calls
 * - Informational panel explaining how the setting works
 * - Timestamp display for transparency and debugging
 * - Real-time cron validation with next run times preview
 *
 * Integration:
 * - Uses Next.js API proxy routes for backend communication
 * - Follows FastAPI error response format for consistent error handling
 * - Syncs with YAML configuration automatically via backend
 */
export function Settings() {
  // Default video limit state (Story 3)
  const [defaultLimit, setDefaultLimit] = useState<number>(10)
  const [originalLimit, setOriginalLimit] = useState<number>(10)
  const [loading, setLoading] = useState<boolean>(true)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<string>('')
  const [lastUpdated, setLastUpdated] = useState<string>('')

  // Scheduler state (Story 007)
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null)
  const [cronExpression, setCronExpression] = useState<string>('0 0 * * *')
  const [originalCronExpression, setOriginalCronExpression] = useState<string>('0 0 * * *')
  const [schedulerEnabled, setSchedulerEnabled] = useState<boolean>(true)
  const [validating, setValidating] = useState<boolean>(false)
  const [validationResult, setValidationResult] = useState<CronValidationResult | null>(null)
  const [schedulerSaving, setSchedulerSaving] = useState<boolean>(false)
  const [schedulerError, setSchedulerError] = useState<string>('')
  const [schedulerSuccess, setSchedulerSuccess] = useState<string>('')
  const [hasChannels, setHasChannels] = useState<boolean>(true)

  /**
   * Fetch current default video limit setting from backend API.
   * 
   * This function implements the "load current settings" part of User Story 3.
   * It handles various error scenarios gracefully and provides specific error
   * messages based on the type of failure.
   * 
   * Error Handling Strategy:
   * - Network errors: Check connection and try again
   * - Backend unavailable: Service-level issue
   * - Other errors: Display the specific error message
   * 
   * Uses Next.js API proxy route (/api/v1/settings/default-video-limit)
   * which forwards to FastAPI backend (/api/v1/settings/default-video-limit)
   */
  const fetchDefaultLimit = async () => {
    try {
      setLoading(true)
      setError('')

      const response = await fetch('/api/v1/settings/default-video-limit')
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch default video limit')
      }

      const data: DefaultVideoLimitSettings = await response.json()
      setDefaultLimit(data.limit)
      setOriginalLimit(data.limit)
      setLastUpdated(new Date(data.updated_at).toLocaleString())
      
    } catch (err) {
      console.error('Error fetching default limit:', err)
      
      // Provide more specific error messages based on error type
      let errorMessage = 'Failed to load settings'
      if (err instanceof Error) {
        if (err.message.includes('Backend service unavailable')) {
          errorMessage = 'Backend service is unavailable. Please try again later.'
        } else if (err.message.includes('Failed to fetch')) {
          errorMessage = 'Network error. Please check your connection and try again.'
        } else {
          errorMessage = err.message
        }
      }
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  /**
   * Save updated default video limit to backend API.
   * 
   * This function implements the "update default setting" part of User Story 3.
   * It validates the input, sends the update to the backend, and provides
   * user feedback through success/error messages.
   * 
   * Features:
   * - Validates input range (1-100) before sending to API
   * - Updates local state with server response (source of truth)
   * - Auto-clears success message after 3 seconds
   * - Provides specific error messages for different failure types
   * - Updates "original" value to reset change detection
   * 
   * API Integration:
   * - Sends PUT request to Next.js proxy route
   * - Expects DefaultVideoLimitResponse format back
   * - Handles Pydantic validation errors (422 responses)
   */
  const saveDefaultLimit = async () => {
    try {
      setSaving(true)
      setError('')
      setSuccess('')

      const response = await fetch('/api/v1/settings/default-video-limit', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ limit: defaultLimit }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update default video limit')
      }

      const data: DefaultVideoLimitSettings = await response.json()
      setOriginalLimit(data.limit)
      setLastUpdated(new Date(data.updated_at).toLocaleString())
      setSuccess(`Default video limit updated to ${data.limit} videos`)
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000)
      
    } catch (err) {
      console.error('Error saving default limit:', err)
      
      // Provide more specific error messages for save operations
      let errorMessage = 'Failed to save settings'
      if (err instanceof Error) {
        if (err.message.includes('Backend service unavailable')) {
          errorMessage = 'Backend service is unavailable. Please try again later.'
        } else if (err.message.includes('Failed to fetch')) {
          errorMessage = 'Network error. Please check your connection and try again.'
        } else if (err.message.includes('Input should be')) {
          errorMessage = 'Invalid value. Please enter a number between 1 and 100.'
        } else {
          errorMessage = err.message
        }
      }
      setError(errorMessage)
    } finally {
      setSaving(false)
    }
  }

  /**
   * Fetch scheduler status and configuration from backend API (Story 007).
   *
   * Retrieves current scheduler state including enabled status, cron schedule,
   * and next/last run times for display in the UI.
   */
  const fetchSchedulerStatus = async () => {
    try {
      const response = await fetch('/api/v1/scheduler/status')

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch scheduler status')
      }

      const data: SchedulerStatus = await response.json()
      setSchedulerStatus(data)
      setSchedulerEnabled(data.scheduler_enabled)

      // Set cron expression (default if not set)
      const schedule = data.cron_schedule || '0 0 * * *'
      setCronExpression(schedule)
      setOriginalCronExpression(schedule)

      // Validate the current schedule to show next runs
      if (schedule) {
        validateCronExpression(schedule)
      }
    } catch (err) {
      console.error('Error fetching scheduler status:', err)
      setSchedulerError(err instanceof Error ? err.message : 'Failed to load scheduler status')
    }
  }

  /**
   * Check if channels exist to determine if scheduler should be enabled (Story 007).
   *
   * The scheduler should be disabled when no channels are configured, as there
   * is nothing to download.
   */
  const checkChannelsExist = async () => {
    try {
      const response = await fetch('/api/v1/channels')
      if (response.ok) {
        const channels = await response.json()
        setHasChannels(Array.isArray(channels) && channels.length > 0)
      }
    } catch (err) {
      console.error('Error checking channels:', err)
      // Assume channels exist if check fails to avoid blocking UI
      setHasChannels(true)
    }
  }

  /**
   * Validate cron expression without saving (Story 007).
   *
   * Called on input change with debouncing to provide real-time feedback.
   * Shows next 5 run times and human-readable description.
   */
  const validateCronExpression = useCallback(async (expression: string) => {
    if (!expression || expression.trim() === '') {
      setValidationResult(null)
      return
    }

    try {
      setValidating(true)
      setSchedulerError('')

      const response = await fetch(
        `/api/v1/scheduler/validate?expression=${encodeURIComponent(expression)}`
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Validation failed')
      }

      const data: CronValidationResult = await response.json()
      setValidationResult(data)
    } catch (err) {
      console.error('Error validating cron expression:', err)
      setValidationResult({
        valid: false,
        error: err instanceof Error ? err.message : 'Validation error',
        next_run: null,
        next_5_runs: [],
        time_until_next: null,
        human_readable: 'Invalid expression'
      })
    } finally {
      setValidating(false)
    }
  }, [])

  /**
   * Save updated cron schedule to backend (Story 007).
   *
   * Validates and updates the scheduler with the new cron expression.
   * Returns next 5 run times for user confirmation.
   */
  const saveSchedule = async () => {
    try {
      setSchedulerSaving(true)
      setSchedulerError('')
      setSchedulerSuccess('')

      const response = await fetch('/api/v1/scheduler/schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cron_expression: cronExpression }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update schedule')
      }

      const data = await response.json()
      setOriginalCronExpression(cronExpression)
      setSchedulerSuccess(
        `Schedule updated successfully: ${data.human_readable}`
      )

      // Update validation result with response data
      setValidationResult({
        valid: true,
        error: null,
        next_run: data.next_run,
        next_5_runs: data.next_5_runs,
        time_until_next: null,
        human_readable: data.human_readable
      })

      // Clear success message after 3 seconds
      setTimeout(() => setSchedulerSuccess(''), 3000)
    } catch (err) {
      console.error('Error saving schedule:', err)
      setSchedulerError(
        err instanceof Error ? err.message : 'Failed to save schedule'
      )
    } finally {
      setSchedulerSaving(false)
    }
  }

  /**
   * Toggle scheduler enabled/disabled state (Story 007).
   *
   * Preserves the cron schedule configuration while enabling/disabling
   * scheduled downloads.
   */
  const toggleScheduler = async (enabled: boolean) => {
    try {
      setSchedulerError('')
      setSchedulerSuccess('')

      const response = await fetch('/api/v1/scheduler/enable', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to toggle scheduler')
      }

      const data = await response.json()
      setSchedulerEnabled(enabled)
      setSchedulerSuccess(data.message)

      // Clear success message after 3 seconds
      setTimeout(() => setSchedulerSuccess(''), 3000)
    } catch (err) {
      console.error('Error toggling scheduler:', err)
      setSchedulerError(
        err instanceof Error ? err.message : 'Failed to toggle scheduler'
      )
    }
  }

  /**
   * Handle cron expression input change with debounced validation.
   *
   * Validates the expression after 500ms of no typing to reduce API calls.
   */
  useEffect(() => {
    const timer = setTimeout(() => {
      if (cronExpression !== originalCronExpression) {
        validateCronExpression(cronExpression)
      }
    }, 500)

    return () => clearTimeout(timer)
  }, [cronExpression, originalCronExpression, validateCronExpression])

  // Load settings on component mount
  useEffect(() => {
    Promise.all([
      fetchDefaultLimit(),
      fetchSchedulerStatus(),
      checkChannelsExist()
    ])
  }, [])

  /**
   * Handle input change with real-time validation.
   * 
   * This function provides immediate feedback as the user types, implementing
   * the "real-time validation" UX pattern. It only updates state for valid
   * values and clears error messages when input becomes valid.
   * 
   * Validation Logic:
   * - Accept only numbers between 1-100 (inclusive)
   * - Reset to default (10) if input is cleared
   * - Clear validation errors when input becomes valid
   * - Ignore invalid inputs (prevents broken UI state)
   * 
   * UX Benefits:
   * - Immediate feedback prevents user confusion
   * - No need to wait for form submission to see validation errors
   * - Graceful handling of edge cases (empty input, non-numbers)
   */
  const handleLimitChange = (value: string) => {
    const numValue = parseInt(value)
    if (!isNaN(numValue) && numValue >= 1 && numValue <= 100) {
      setDefaultLimit(numValue)
      setError('') // Clear any validation errors
    } else if (value === '') {
      setDefaultLimit(10) // Reset to default if empty
    }
  }

  // Check if settings have changed
  const hasChanges = defaultLimit !== originalLimit

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center mb-6">
          <SettingsIcon className="h-6 w-6 mr-3 text-blue-600" />
          <h2 className="text-2xl font-bold text-gray-900">Application Settings</h2>
        </div>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full"></div>
          <span className="ml-3 text-gray-600">Loading settings...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center mb-6">
        <SettingsIcon className="h-6 w-6 mr-3 text-blue-600" />
        <h2 className="text-2xl font-bold text-gray-900">Application Settings</h2>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-600 mr-2" />
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center">
            <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
            <span className="text-green-800">{success}</span>
          </div>
        </div>
      )}

      {/* Default Video Limit Setting */}
      <div className="space-y-6">
        <div>
          <label htmlFor="defaultLimit" className="block text-sm font-medium text-gray-700 mb-2">
            Default Video Limit
          </label>
          <div className="flex items-start space-x-4">
            <div className="flex-1">
              <input
                type="number"
                id="defaultLimit"
                min="1"
                max="100"
                value={defaultLimit}
                onChange={(e) => handleLimitChange(e.target.value)}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={saving}
              />
              <p className="mt-1 text-sm text-gray-500">
                Number of videos to keep per channel (1-100)
              </p>
            </div>
            <button
              onClick={saveDefaultLimit}
              disabled={!hasChanges || saving || defaultLimit < 1 || defaultLimit > 100}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save
                </>
              )}
            </button>
          </div>
        </div>

        {/* Information Panel */}
        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="flex items-start">
            <Info className="h-5 w-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-2">How Default Video Limit Works:</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>Applied automatically to new channels when no custom limit is specified</li>
                <li>Existing channels keep their current limits and are not affected</li>
                <li>Can be overridden for individual channels after creation</li>
                <li>Synced to YAML configuration file for backup and transparency</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Last Updated Info */}
        {lastUpdated && (
          <div className="text-sm text-gray-500">
            Last updated: {lastUpdated}
          </div>
        )}

        {/* Divider */}
        <div className="border-t border-gray-200 my-8"></div>

        {/* Scheduler Section (Story 007) */}
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
              <Calendar className="h-5 w-5 mr-2 text-blue-600" />
              Automatic Download Scheduler
            </h3>

            {/* Scheduler Error Message */}
            {schedulerError && (
              <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-red-600 mr-2" />
                  <span className="text-red-800">{schedulerError}</span>
                </div>
              </div>
            )}

            {/* Scheduler Success Message */}
            {schedulerSuccess && (
              <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-md">
                <div className="flex items-center">
                  <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
                  <span className="text-green-800">{schedulerSuccess}</span>
                </div>
              </div>
            )}

            {/* Enable/Disable Toggle */}
            <div className="mb-4">
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={schedulerEnabled}
                  onChange={(e) => toggleScheduler(e.target.checked)}
                  disabled={!hasChannels}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:opacity-50"
                />
                <span className="text-sm font-medium text-gray-700">
                  Enable automatic scheduled downloads
                </span>
              </label>
              {!hasChannels && (
                <p className="mt-1 text-sm text-yellow-600">
                  Add channels before enabling the scheduler
                </p>
              )}
            </div>

            {/* Cron Schedule Input */}
            <div>
              <label htmlFor="cronSchedule" className="block text-sm font-medium text-gray-700 mb-2">
                Schedule (Cron Expression)
              </label>
              <div className="flex items-start space-x-4">
                <div className="flex-1">
                  <input
                    type="text"
                    id="cronSchedule"
                    value={cronExpression}
                    onChange={(e) => setCronExpression(e.target.value)}
                    placeholder="0 0 * * *"
                    disabled={!hasChannels || schedulerSaving}
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    Default: Daily at midnight (0 0 * * *)
                  </p>

                  {/* Real-time Validation Feedback */}
                  {validating && (
                    <div className="mt-2 flex items-center text-sm text-gray-600">
                      <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full mr-2"></div>
                      Validating...
                    </div>
                  )}

                  {!validating && validationResult && (
                    <div className="mt-2">
                      {validationResult.valid ? (
                        <div className="space-y-2">
                          <div className="flex items-center text-sm text-green-600">
                            <CheckCircle className="h-4 w-4 mr-2" />
                            <span className="font-medium">{validationResult.human_readable}</span>
                          </div>
                          {validationResult.next_5_runs && validationResult.next_5_runs.length > 0 && (
                            <div className="bg-green-50 border border-green-200 rounded-md p-3">
                              <p className="text-sm font-medium text-green-900 mb-2 flex items-center">
                                <Clock className="h-4 w-4 mr-2" />
                                Next 5 scheduled runs:
                              </p>
                              <ul className="space-y-1 text-sm text-green-800">
                                {validationResult.next_5_runs.map((run, index) => (
                                  <li key={index} className="font-mono">
                                    {new Date(run).toLocaleString()}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-start text-sm text-red-600">
                          <AlertCircle className="h-4 w-4 mr-2 mt-0.5 flex-shrink-0" />
                          <span>{validationResult.error || 'Invalid cron expression'}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <button
                  onClick={saveSchedule}
                  disabled={
                    !hasChannels ||
                    schedulerSaving ||
                    cronExpression === originalCronExpression ||
                    !validationResult?.valid
                  }
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {schedulerSaving ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Schedule
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Cron Expression Help Panel */}
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-start">
              <Info className="h-5 w-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-2">Common Cron Patterns:</p>
                <ul className="space-y-1 list-disc list-inside">
                  <li><code className="bg-blue-100 px-1 rounded">0 */6 * * *</code> - Every 6 hours</li>
                  <li><code className="bg-blue-100 px-1 rounded">0 0 * * *</code> - Daily at midnight</li>
                  <li><code className="bg-blue-100 px-1 rounded">0 9 * * 1-5</code> - Weekdays at 9 AM</li>
                  <li><code className="bg-blue-100 px-1 rounded">*/15 * * * *</code> - Every 15 minutes</li>
                </ul>
                <p className="mt-2 text-xs">
                  Format: minute hour day month day-of-week
                  <br />
                  Minimum interval: 5 minutes
                </p>
              </div>
            </div>
          </div>

          {/* Current Status Display */}
          {schedulerStatus && (
            <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
              <p className="text-sm font-medium text-gray-900 mb-2">Current Status:</p>
              <div className="space-y-1 text-sm text-gray-700">
                <div className="flex items-center">
                  <span className="font-medium mr-2">Scheduler:</span>
                  {schedulerStatus.scheduler_enabled ? (
                    <span className="text-green-600 font-medium">Enabled</span>
                  ) : (
                    <span className="text-gray-500">Disabled</span>
                  )}
                </div>
                {schedulerStatus.next_run && (
                  <div className="flex items-center">
                    <span className="font-medium mr-2">Next run:</span>
                    <span>{new Date(schedulerStatus.next_run).toLocaleString()}</span>
                  </div>
                )}
                {schedulerStatus.last_run && (
                  <div className="flex items-center">
                    <span className="font-medium mr-2">Last run:</span>
                    <span>{new Date(schedulerStatus.last_run).toLocaleString()}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}