import React, { useState, useEffect } from 'react'
import {
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  Pause,
  Play,
  Settings as SettingsIcon,
  AlertCircle,
  RefreshCw
} from 'lucide-react'

/**
 * Interface for scheduler status from API (Story 007 - FE-002).
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
 * Props for the SchedulerStatusWidget component.
 */
interface SchedulerStatusWidgetProps {
  onNavigateToSettings?: () => void
}

/**
 * SchedulerStatusWidget Component for Story 007 - FE-002.
 *
 * Displays current scheduler status on the Dashboard for at-a-glance monitoring.
 * Shows current schedule, last/next run times, and provides quick access to
 * configuration in Settings.
 *
 * Features:
 * - Auto-refresh every 30 seconds
 * - Human-readable cron schedule display
 * - Relative time formatting ("2 hours ago", "in 3 hours")
 * - Live countdown to next run
 * - Status indicators (Active, Paused, Running, No Schedule)
 * - Link to Settings for configuration
 * - Loading and error states with retry
 * - Responsive design (collapsible on mobile)
 *
 * Architecture:
 * - Polls /api/v1/scheduler/status every 30 seconds
 * - Updates countdown timer every second
 * - Graceful error handling with retry button
 */
export function SchedulerStatusWidget({ onNavigateToSettings }: SchedulerStatusWidgetProps) {
  const [status, setStatus] = useState<SchedulerStatus | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string>('')
  const [timeUntilNext, setTimeUntilNext] = useState<string>('')
  const [lastRunRelative, setLastRunRelative] = useState<string>('')
  const [isExpanded, setIsExpanded] = useState<boolean>(true)

  /**
   * Fetch scheduler status from API.
   */
  const fetchStatus = async () => {
    try {
      setError('')
      const response = await fetch('/api/v1/scheduler/status')

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to fetch scheduler status')
      }

      const data: SchedulerStatus = await response.json()
      setStatus(data)
    } catch (err) {
      console.error('Error fetching scheduler status:', err)
      setError(err instanceof Error ? err.message : 'Failed to load scheduler status')
    } finally {
      setLoading(false)
    }
  }

  /**
   * Calculate relative time from timestamp (e.g., "2 hours ago", "in 3 hours").
   */
  const getRelativeTime = (timestamp: string | null, isFuture: boolean = false): string => {
    if (!timestamp) return 'Never'

    const now = new Date()
    const time = new Date(timestamp)
    const diffMs = Math.abs(time.getTime() - now.getTime())

    const minutes = Math.floor(diffMs / 60000)
    const hours = Math.floor(minutes / 60)
    const days = Math.floor(hours / 24)

    if (days > 0) {
      return isFuture ? `in ${days} day${days > 1 ? 's' : ''}` : `${days} day${days > 1 ? 's' : ''} ago`
    } else if (hours > 0) {
      return isFuture ? `in ${hours} hour${hours > 1 ? 's' : ''}` : `${hours} hour${hours > 1 ? 's' : ''} ago`
    } else if (minutes > 0) {
      return isFuture ? `in ${minutes} minute${minutes > 1 ? 's' : ''}` : `${minutes} minute${minutes > 1 ? 's' : ''} ago`
    } else {
      return isFuture ? 'in less than a minute' : 'just now'
    }
  }

  /**
   * Get human-readable description of cron schedule.
   */
  const getCronDescription = (cronExpr: string | null): string => {
    if (!cronExpr) return 'No schedule set'

    const commonPatterns: { [key: string]: string } = {
      '0 * * * *': 'Every hour',
      '0 */6 * * *': 'Every 6 hours',
      '0 0 * * *': 'Daily at midnight',
      '0 0 * * 0': 'Weekly on Sunday',
      '*/15 * * * *': 'Every 15 minutes',
      '0 9 * * 1-5': 'Weekdays at 9 AM'
    }

    return commonPatterns[cronExpr] || cronExpr
  }

  /**
   * Get status badge based on scheduler state.
   */
  const getStatusBadge = () => {
    if (!status) return null

    if (!status.scheduler_enabled) {
      return (
        <div className="flex items-center text-gray-500">
          <Pause className="h-4 w-4 mr-1" />
          <span className="text-sm font-medium">Paused</span>
        </div>
      )
    }

    if (status.scheduler_running) {
      return (
        <div className="flex items-center text-blue-600">
          <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
          <span className="text-sm font-medium">Running Job</span>
        </div>
      )
    }

    if (!status.cron_schedule) {
      return (
        <div className="flex items-center text-yellow-600">
          <AlertCircle className="h-4 w-4 mr-1" />
          <span className="text-sm font-medium">No Schedule</span>
        </div>
      )
    }

    return (
      <div className="flex items-center text-green-600">
        <CheckCircle className="h-4 w-4 mr-1" />
        <span className="text-sm font-medium">Active</span>
      </div>
    )
  }

  /**
   * Update countdown timer and relative times.
   */
  useEffect(() => {
    if (!status) return

    const updateTimes = () => {
      if (status.next_run) {
        setTimeUntilNext(getRelativeTime(status.next_run, true))
      }
      if (status.last_run) {
        setLastRunRelative(getRelativeTime(status.last_run, false))
      }
    }

    updateTimes()
    const timer = setInterval(updateTimes, 1000)

    return () => clearInterval(timer)
  }, [status])

  /**
   * Auto-refresh status every 30 seconds.
   */
  useEffect(() => {
    fetchStatus()

    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  // Loading State
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-center">
          <div className="animate-spin h-6 w-6 border-4 border-blue-600 border-t-transparent rounded-full"></div>
          <span className="ml-3 text-gray-600">Loading scheduler status...</span>
        </div>
      </div>
    )
  }

  // Error State
  if (error) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center text-red-600">
            <AlertCircle className="h-5 w-5 mr-2" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchStatus}
            className="px-3 py-1 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 transition"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!status) return null

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <Calendar className="h-5 w-5 mr-2 text-blue-600" />
          <h3 className="text-lg font-medium text-gray-900">Scheduler Status</h3>
        </div>
        <div className="flex items-center space-x-3">
          {getStatusBadge()}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="lg:hidden text-gray-500 hover:text-gray-700"
          >
            {isExpanded ? '−' : '+'}
          </button>
        </div>
      </div>

      {/* Content (collapsible on mobile) */}
      <div className={`space-y-4 ${isExpanded ? 'block' : 'hidden lg:block'}`}>
        {/* Current Schedule */}
        <div className="bg-gray-50 rounded-md p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Current Schedule:</span>
            <span className="text-sm text-gray-900 font-medium">
              {getCronDescription(status.cron_schedule)}
            </span>
          </div>
          {status.cron_schedule && (
            <p className="text-xs text-gray-500 font-mono text-right">{status.cron_schedule}</p>
          )}
        </div>

        {/* Next Run */}
        {status.scheduler_enabled && status.next_run && (
          <div className="flex items-start justify-between">
            <div className="flex items-center text-gray-700">
              <Clock className="h-4 w-4 mr-2 text-blue-600" />
              <span className="text-sm font-medium">Next run:</span>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-900">{new Date(status.next_run).toLocaleString()}</p>
              <p className="text-xs text-blue-600 font-medium">{timeUntilNext}</p>
            </div>
          </div>
        )}

        {/* Last Run */}
        {status.last_run && (
          <div className="flex items-start justify-between">
            <div className="flex items-center text-gray-700">
              <CheckCircle className="h-4 w-4 mr-2 text-green-600" />
              <span className="text-sm font-medium">Last run:</span>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-900">{new Date(status.last_run).toLocaleString()}</p>
              <p className="text-xs text-gray-500">{lastRunRelative}</p>
            </div>
          </div>
        )}

        {/* No Schedule Warning */}
        {!status.cron_schedule && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-yellow-600 mr-2 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-yellow-800">
                <p className="font-medium">No schedule configured</p>
                <p className="mt-1">Configure a cron schedule in Settings to enable automatic downloads.</p>
              </div>
            </div>
          </div>
        )}

        {/* Paused Warning */}
        {!status.scheduler_enabled && status.cron_schedule && (
          <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
            <div className="flex items-start">
              <Pause className="h-5 w-5 text-gray-500 mr-2 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-gray-700">
                <p className="font-medium">Scheduler is paused</p>
                <p className="mt-1">Enable the scheduler in Settings to resume automatic downloads.</p>
              </div>
            </div>
          </div>
        )}

        {/* Link to Settings */}
        <div className="pt-4 border-t border-gray-200">
          <button
            onClick={onNavigateToSettings}
            className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition"
          >
            <SettingsIcon className="h-4 w-4 mr-2" />
            Configure Schedule
          </button>
        </div>
      </div>
    </div>
  )
}
