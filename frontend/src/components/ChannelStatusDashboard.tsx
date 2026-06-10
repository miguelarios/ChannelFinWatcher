import React, { useState, useEffect, useCallback } from 'react'
import {
  LayoutDashboardIcon,
  RefreshCwIcon,
  SearchIcon,
  HardDriveIcon,
  YoutubeIcon,
  AlertTriangleIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  PauseCircleIcon,
  ClockIcon,
  VideoIcon,
  PlusIcon,
} from 'lucide-react'
import { SchedulerStatusWidget } from './SchedulerStatusWidget'

/**
 * ChannelStatusDashboard Component - Landing page with channel health + storage
 *
 * Implements User Story 9 (Channel Status Dashboard) and the core of
 * User Story 12 (Storage Usage Monitoring):
 * - Storage overview with capacity bar and warning banner at >= 80% usage
 * - System totals (channels, videos, storage)
 * - Card grid of all channels: status indicator, video count vs limit,
 *   storage used, last check time, last run outcome
 * - Search filter, sort selector, quick enable/disable toggle per card
 * - Auto-refreshes every 30 seconds
 *
 * Technical Details:
 * - Uses GET /api/v1/dashboard (single aggregated round-trip)
 * - Enable/disable uses PUT /api/v1/channels/{id} and refetches
 */

interface DiskUsage {
  total_bytes: number
  used_bytes: number
  free_bytes: number
  usage_percent: number
  warning: boolean
}

interface ChannelSummary {
  id: number
  name: string
  url: string
  enabled: boolean
  limit: number
  metadata_status: string
  video_count: number
  storage_bytes: number
  last_check?: string
  last_run_status?: string
  last_run_date?: string
  last_run_error?: string
}

interface DashboardData {
  disk: DiskUsage | null
  totals: {
    channels: number
    enabled_channels: number
    videos: number
    storage_bytes: number
  }
  channels: ChannelSummary[]
  generated_at: string
}

type SortKey = 'recent' | 'storage' | 'name'

const REFRESH_INTERVAL_MS = 30000

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function formatRelativeTime(isoDate?: string): string {
  if (!isoDate) return 'Never'
  const date = new Date(isoDate.endsWith('Z') ? isoDate : `${isoDate}Z`)
  if (isNaN(date.getTime())) return 'Never'
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'Just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** Health status drives the colored indicator dot and label on each card. */
function channelHealth(channel: ChannelSummary): { color: string; label: string } {
  if (!channel.enabled) return { color: 'bg-gray-400', label: 'Disabled' }
  if (channel.last_run_status === 'failed') return { color: 'bg-red-500', label: 'Last run failed' }
  if (!channel.last_check) return { color: 'bg-yellow-400', label: 'Never checked' }
  return { color: 'bg-green-500', label: 'Active' }
}

function capacityBarColor(percent: number): string {
  if (percent >= 80) return 'bg-red-500'
  if (percent >= 70) return 'bg-yellow-500'
  return 'bg-green-500'
}

interface ChannelStatusDashboardProps {
  onNavigateToChannels?: () => void
  onNavigateToSettings?: () => void
}

export function ChannelStatusDashboard({
  onNavigateToChannels,
  onNavigateToSettings,
}: ChannelStatusDashboardProps) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('recent')
  const [togglingChannelId, setTogglingChannelId] = useState<number | null>(null)

  const fetchDashboard = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsLoading(true)
    try {
      const response = await fetch('/api/v1/dashboard')
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || body.error || 'Failed to load dashboard')
      }
      setData(await response.json())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDashboard(true)
    const interval = setInterval(() => fetchDashboard(false), REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchDashboard])

  const handleToggleEnabled = async (channel: ChannelSummary) => {
    setTogglingChannelId(channel.id)
    try {
      const response = await fetch(`/api/v1/channels/${channel.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !channel.enabled }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        throw new Error(body.detail || 'Failed to update channel')
      }
      await fetchDashboard(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update channel')
    } finally {
      setTogglingChannelId(null)
    }
  }

  const visibleChannels = (data?.channels || [])
    .filter((channel) => {
      if (!search) return true
      const query = search.toLowerCase()
      return channel.name.toLowerCase().includes(query) || channel.url.toLowerCase().includes(query)
    })
    .sort((a, b) => {
      switch (sortKey) {
        case 'storage':
          return b.storage_bytes - a.storage_bytes
        case 'name':
          return a.name.localeCompare(b.name)
        default:
          // API already returns most-recently-checked first
          return 0
      }
    })

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <SchedulerStatusWidget onNavigateToSettings={onNavigateToSettings} />

      {/* Storage warning banner (US-012: warn at >= 80% capacity) */}
      {data?.disk?.warning && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
          <AlertTriangleIcon className="h-5 w-5 text-red-500 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">
              Storage is {data.disk.usage_percent}% full
            </p>
            <p className="text-sm text-red-700">
              Only {formatBytes(data.disk.free_bytes)} remaining. Consider lowering video limits
              on your largest channels below.
            </p>
          </div>
        </div>
      )}

      {/* Overview row: storage + totals */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow-md p-5">
          <div className="flex items-center mb-3">
            <HardDriveIcon className="h-5 w-5 mr-2 text-gray-500" />
            <h3 className="font-semibold text-gray-900">Storage</h3>
          </div>
          {data?.disk ? (
            <>
              <div className="w-full bg-gray-100 rounded-full h-3 mb-2" role="progressbar"
                aria-valuenow={data.disk.usage_percent} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className={`h-3 rounded-full ${capacityBarColor(data.disk.usage_percent)}`}
                  style={{ width: `${Math.min(100, data.disk.usage_percent)}%` }}
                />
              </div>
              <p className="text-sm text-gray-700">
                {formatBytes(data.disk.used_bytes)} of {formatBytes(data.disk.total_bytes)} used
                ({data.disk.usage_percent}%)
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {formatBytes(data.disk.free_bytes)} free &middot; videos use {formatBytes(data.totals.storage_bytes)}
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">Disk information unavailable</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow-md p-5">
          <div className="flex items-center mb-3">
            <YoutubeIcon className="h-5 w-5 mr-2 text-gray-500" />
            <h3 className="font-semibold text-gray-900">Library</h3>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900">{data?.totals.channels ?? '—'}</p>
              <p className="text-xs text-gray-500">
                Channels ({data?.totals.enabled_channels ?? 0} enabled)
              </p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{data?.totals.videos ?? '—'}</p>
              <p className="text-xs text-gray-500">Videos</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {data ? formatBytes(data.totals.storage_bytes) : '—'}
              </p>
              <p className="text-xs text-gray-500">Video storage</p>
            </div>
          </div>
        </div>
      </div>

      {/* Channel cards */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center">
            <LayoutDashboardIcon className="h-6 w-6 mr-2 text-red-600" />
            <h2 className="text-xl font-semibold text-gray-900">Channel Status</h2>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <SearchIcon className="h-4 w-4 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search channels..."
                aria-label="Search channels"
                className="pl-8 pr-3 py-1.5 w-48 rounded-md border border-gray-300 text-sm focus:border-red-500 focus:ring-red-500"
              />
            </div>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              aria-label="Sort channels"
              className="rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-red-500 focus:ring-red-500"
            >
              <option value="recent">Recently checked</option>
              <option value="storage">Largest storage</option>
              <option value="name">Name</option>
            </select>
            <button
              onClick={() => fetchDashboard(true)}
              disabled={isLoading}
              className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
            >
              <RefreshCwIcon className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-start">
            <AlertCircleIcon className="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {isLoading && !data ? (
          <div className="py-12 text-center text-gray-500">
            <RefreshCwIcon className="h-8 w-8 mx-auto mb-3 animate-spin text-gray-400" />
            <p>Loading dashboard...</p>
          </div>
        ) : visibleChannels.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            <YoutubeIcon className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            {data && data.channels.length > 0 ? (
              <p>No channels match your search.</p>
            ) : (
              <>
                <p className="font-medium text-gray-700 mb-1">No channels yet</p>
                <p className="text-sm mb-4">Add a YouTube channel to start monitoring.</p>
                {onNavigateToChannels && (
                  <button
                    onClick={onNavigateToChannels}
                    className="inline-flex items-center px-4 py-2 rounded-md text-sm font-medium text-white bg-red-600 hover:bg-red-700 transition-colors"
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    Add Channel
                  </button>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {visibleChannels.map((channel) => {
              const health = channelHealth(channel)
              return (
                <div
                  key={channel.id}
                  className={`border rounded-lg p-4 ${channel.enabled ? 'border-gray-200' : 'border-gray-200 bg-gray-50 opacity-75'}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="min-w-0 mr-2">
                      <p className="font-medium text-gray-900 truncate" title={channel.name}>
                        {channel.name || channel.url}
                      </p>
                      <p className="flex items-center text-xs text-gray-500 mt-0.5">
                        <span className={`inline-block h-2 w-2 rounded-full mr-1.5 ${health.color}`} aria-hidden="true" />
                        {health.label}
                      </p>
                    </div>
                    <button
                      onClick={() => handleToggleEnabled(channel)}
                      disabled={togglingChannelId === channel.id}
                      title={channel.enabled ? 'Disable monitoring' : 'Enable monitoring'}
                      className="text-gray-400 hover:text-gray-600 disabled:opacity-50 flex-shrink-0"
                    >
                      {channel.enabled ? (
                        <PauseCircleIcon className="h-5 w-5" />
                      ) : (
                        <CheckCircleIcon className="h-5 w-5" />
                      )}
                    </button>
                  </div>

                  <div className="space-y-1 text-sm text-gray-700">
                    <p className="flex items-center">
                      <VideoIcon className="h-4 w-4 mr-1.5 text-gray-400" />
                      {channel.video_count}/{channel.limit} videos
                    </p>
                    <p className="flex items-center">
                      <HardDriveIcon className="h-4 w-4 mr-1.5 text-gray-400" />
                      {formatBytes(channel.storage_bytes)}
                    </p>
                    <p className="flex items-center">
                      <ClockIcon className="h-4 w-4 mr-1.5 text-gray-400" />
                      Checked {formatRelativeTime(channel.last_check)}
                    </p>
                  </div>

                  {channel.last_run_status === 'failed' && channel.last_run_error && (
                    <p className="text-xs text-red-600 mt-2 line-clamp-2" title={channel.last_run_error}>
                      {channel.last_run_error}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
