import React, { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle, Play, Pause, X, FileText, Loader } from 'lucide-react'

/**
 * Interface for NFO backfill needed response from API.
 */
interface BackfillNeededResponse {
  backfill_needed: boolean
  channels_needing_backfill: number
}

/**
 * Interface for NFO backfill status response from API.
 */
interface BackfillStatus {
  is_running: boolean
  is_paused: boolean
  total_channels: number
  processed_channels: number
  current_channel_name: string | null
  files_created: number
  files_updated: number
  files_failed: number
  started_at: string | null
  completed_at: string | null
}

/**
 * NfoBackfillManager Component
 *
 * Manages NFO file backfill operations for existing channels.
 *
 * Features:
 * - Detects channels needing NFO backfill (nfo_last_generated IS NULL)
 * - Displays prominent notification banner when backfill needed
 * - Real-time progress tracking during backfill
 * - Pause/Resume functionality
 * - Dismissible banner (stored in localStorage)
 * - Automatic polling for status updates
 *
 * Integration:
 * - Uses Next.js API proxy routes for backend communication
 * - Polls status every 2 seconds while backfill is running
 * - Cleans up polling interval when component unmounts
 */
export function NfoBackfillManager() {
  // Backfill detection state
  const [backfillNeeded, setBackfillNeeded] = useState<boolean>(false)
  const [channelsNeeded, setChannelsNeeded] = useState<number>(0)
  const [bannerDismissed, setBannerDismissed] = useState<boolean>(false)

  // Backfill status state
  const [backfillStatus, setBackfillStatus] = useState<BackfillStatus | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<string>('')

  /**
   * Check if backfill is needed on component mount.
   */
  const checkBackfillNeeded = async () => {
    try {
      const response = await fetch('/api/v1/nfo/backfill/needed')

      if (!response.ok) {
        throw new Error('Failed to check backfill status')
      }

      const data: BackfillNeededResponse = await response.json()
      setBackfillNeeded(data.backfill_needed)
      setChannelsNeeded(data.channels_needing_backfill)

      // Check if user has dismissed the banner before
      const dismissed = localStorage.getItem('nfo_backfill_dismissed')
      if (dismissed === 'true' && !data.backfill_needed) {
        // Clear dismissal if backfill is no longer needed
        localStorage.removeItem('nfo_backfill_dismissed')
      }
      setBannerDismissed(dismissed === 'true')

    } catch (err) {
      console.error('Error checking backfill status:', err)
      setError(err instanceof Error ? err.message : 'Failed to check backfill status')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Fetch current backfill status from backend.
   */
  const fetchBackfillStatus = async () => {
    try {
      const response = await fetch('/api/v1/nfo/backfill/status')

      if (!response.ok) {
        throw new Error('Failed to fetch backfill status')
      }

      const data: BackfillStatus = await response.json()
      setBackfillStatus(data)

      // If backfill completed, show success message and refresh needed status
      if (data.completed_at && !data.is_running) {
        setSuccess(
          `NFO backfill complete: ${data.total_channels} channels, ${data.files_created} files created`
        )
        // Refresh backfill needed status
        await checkBackfillNeeded()

        // Clear success message after 5 seconds
        setTimeout(() => setSuccess(''), 5000)
      }

    } catch (err) {
      console.error('Error fetching backfill status:', err)
      // Don't set error state here to avoid UI clutter during polling
    }
  }

  /**
   * Start NFO backfill process.
   */
  const startBackfill = async () => {
    try {
      setError('')
      setSuccess('')

      const response = await fetch('/api/v1/nfo/backfill/start', {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to start backfill')
      }

      // Immediately fetch status to show progress
      await fetchBackfillStatus()

    } catch (err) {
      console.error('Error starting backfill:', err)
      setError(err instanceof Error ? err.message : 'Failed to start backfill')
    }
  }

  /**
   * Pause NFO backfill process.
   */
  const pauseBackfill = async () => {
    try {
      setError('')

      const response = await fetch('/api/v1/nfo/backfill/pause', {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to pause backfill')
      }

      await fetchBackfillStatus()

    } catch (err) {
      console.error('Error pausing backfill:', err)
      setError(err instanceof Error ? err.message : 'Failed to pause backfill')
    }
  }

  /**
   * Resume NFO backfill process.
   */
  const resumeBackfill = async () => {
    try {
      setError('')

      const response = await fetch('/api/v1/nfo/backfill/resume', {
        method: 'POST',
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to resume backfill')
      }

      await fetchBackfillStatus()

    } catch (err) {
      console.error('Error resuming backfill:', err)
      setError(err instanceof Error ? err.message : 'Failed to resume backfill')
    }
  }

  /**
   * Dismiss the backfill notification banner.
   */
  const dismissBanner = () => {
    setBannerDismissed(true)
    localStorage.setItem('nfo_backfill_dismissed', 'true')
  }

  // Load initial state on mount
  useEffect(() => {
    checkBackfillNeeded()
    fetchBackfillStatus()
  }, [])

  // Poll for status updates while backfill is running
  useEffect(() => {
    if (!backfillStatus?.is_running) {
      return
    }

    const interval = setInterval(() => {
      fetchBackfillStatus()
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(interval)
  }, [backfillStatus?.is_running])

  if (loading) {
    return null // Don't show anything while loading initial state
  }

  // Calculate progress percentage
  const progressPercentage = backfillStatus && backfillStatus.total_channels > 0
    ? Math.round((backfillStatus.processed_channels / backfillStatus.total_channels) * 100)
    : 0

  return (
    <div className="space-y-4">
      {/* Backfill Needed Banner */}
      {backfillNeeded && !bannerDismissed && !backfillStatus?.is_running && (
        <div className="bg-yellow-50 border border-yellow-300 rounded-md p-4">
          <div className="flex items-start">
            <AlertCircle className="h-5 w-5 text-yellow-600 mr-3 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-yellow-900">
                {channelsNeeded} channel{channelsNeeded !== 1 ? 's' : ''} need NFO files generated
              </p>
              <p className="text-xs text-yellow-700 mt-1">
                Generate Jellyfin-compatible metadata files for existing channels to enable rich media library display.
              </p>
            </div>
            <div className="flex items-center space-x-2 ml-4">
              <button
                onClick={startBackfill}
                className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-yellow-900 bg-yellow-200 hover:bg-yellow-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500"
              >
                <Play className="h-3 w-3 mr-1" />
                Start Backfill
              </button>
              <button
                onClick={dismissBanner}
                className="text-yellow-600 hover:text-yellow-800"
                title="Dismiss"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-600 mr-2" />
            <span className="text-red-800 text-sm">{error}</span>
            <button
              onClick={() => setError('')}
              className="ml-auto text-red-600 hover:text-red-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex items-center">
            <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
            <span className="text-green-800 text-sm">{success}</span>
            <button
              onClick={() => setSuccess('')}
              className="ml-auto text-green-600 hover:text-green-700"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Backfill Progress Indicator */}
      {backfillStatus?.is_running && (
        <div className="bg-blue-50 border border-blue-300 rounded-md p-4">
          <div className="space-y-3">
            {/* Header with controls */}
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <FileText className="h-5 w-5 text-blue-600 mr-2" />
                <span className="text-sm font-medium text-blue-900">
                  Generating NFO files...
                </span>
              </div>
              <div className="flex items-center space-x-2">
                {backfillStatus.is_paused ? (
                  <button
                    onClick={resumeBackfill}
                    className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-blue-900 bg-blue-200 hover:bg-blue-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <Play className="h-3 w-3 mr-1" />
                    Resume
                  </button>
                ) : (
                  <button
                    onClick={pauseBackfill}
                    className="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-blue-900 bg-blue-200 hover:bg-blue-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <Pause className="h-3 w-3 mr-1" />
                    Pause
                  </button>
                )}
              </div>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              ></div>
            </div>

            {/* Progress details */}
            <div className="text-xs text-blue-800 space-y-1">
              <div className="flex justify-between">
                <span>
                  Channel {backfillStatus.processed_channels} of {backfillStatus.total_channels}
                </span>
                <span>{progressPercentage}%</span>
              </div>
              {backfillStatus.current_channel_name && (
                <div className="flex items-center">
                  <Loader className="h-3 w-3 mr-2 animate-spin" />
                  <span className="font-medium">{backfillStatus.current_channel_name}</span>
                </div>
              )}
              {backfillStatus.is_paused && (
                <div className="text-yellow-700 font-medium">
                  Paused - Click Resume to continue
                </div>
              )}
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-blue-200 text-xs">
              <div>
                <span className="text-blue-600">Created:</span>{' '}
                <span className="font-medium text-blue-900">{backfillStatus.files_created}</span>
              </div>
              <div>
                <span className="text-blue-600">Updated:</span>{' '}
                <span className="font-medium text-blue-900">{backfillStatus.files_updated}</span>
              </div>
              <div>
                <span className="text-blue-600">Failed:</span>{' '}
                <span className="font-medium text-red-600">{backfillStatus.files_failed}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
