import React, { useState, useEffect, useCallback } from 'react'
import {
  HistoryIcon,
  RefreshCwIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  DownloadIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  AlertCircleIcon,
} from 'lucide-react'

/**
 * DownloadHistory Component - Cross-channel download history view
 *
 * This component implements User Story 11: Download History View
 *
 * Features:
 * - Lists individual video downloads across all channels (most recent first)
 * - Filter by channel and by download status
 * - Pagination (50 records per page)
 * - Status badges with icons (completed, failed, downloading, pending)
 * - File sizes, timestamps, and error messages for failed downloads
 * - Links to the original video on YouTube
 *
 * Technical Details:
 * - Uses GET /api/v1/downloads with channel_id/status/limit/offset query params
 * - Uses GET /api/v1/channels to populate the channel filter dropdown
 * - Refetches whenever filters or page change
 */

interface DownloadRecord {
  id: number
  channel_id: number
  channel_name?: string
  video_id: string
  title: string
  upload_date?: string
  duration?: string
  file_path?: string
  file_size?: number
  status: string
  error_message?: string
  file_exists: boolean
  deleted_at?: string
  created_at: string
  completed_at?: string
}

interface ChannelOption {
  id: number
  name: string
}

const PAGE_SIZE = 50

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'downloading', label: 'Downloading' },
  { value: 'pending', label: 'Pending' },
]

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function formatDate(isoDate?: string): string {
  if (!isoDate) return '—'
  // Backend stores naive UTC timestamps; append Z so the browser converts to local time
  const date = new Date(isoDate.endsWith('Z') ? isoDate : `${isoDate}Z`)
  if (isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function StatusBadge({ status, fileExists, deletedAt }: { status: string; fileExists: boolean; deletedAt?: string }) {
  if (status === 'completed' && (deletedAt || !fileExists)) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        <CheckCircleIcon className="h-3 w-3 mr-1" />
        Cleaned up
      </span>
    )
  }

  switch (status) {
    case 'completed':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <CheckCircleIcon className="h-3 w-3 mr-1" />
          Completed
        </span>
      )
    case 'failed':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          <XCircleIcon className="h-3 w-3 mr-1" />
          Failed
        </span>
      )
    case 'downloading':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          <DownloadIcon className="h-3 w-3 mr-1" />
          Downloading
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          <ClockIcon className="h-3 w-3 mr-1" />
          Pending
        </span>
      )
  }
}

export function DownloadHistory() {
  const [downloads, setDownloads] = useState<DownloadRecord[]>([])
  const [total, setTotal] = useState(0)
  const [channels, setChannels] = useState<ChannelOption[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  // Filters and pagination
  const [channelFilter, setChannelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(0)

  const fetchDownloads = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      params.set('limit', String(PAGE_SIZE))
      params.set('offset', String(page * PAGE_SIZE))
      if (channelFilter) params.set('channel_id', channelFilter)
      if (statusFilter) params.set('status', statusFilter)

      const response = await fetch(`/api/v1/downloads?${params.toString()}`)
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || data.error || 'Failed to load download history')
      }
      const data = await response.json()
      setDownloads(data.downloads || [])
      setTotal(data.total || 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load download history')
      setDownloads([])
      setTotal(0)
    } finally {
      setIsLoading(false)
    }
  }, [channelFilter, statusFilter, page])

  useEffect(() => {
    fetchDownloads()
  }, [fetchDownloads])

  // Load channels once for the filter dropdown
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        const response = await fetch('/api/v1/channels')
        if (response.ok) {
          const data = await response.json()
          setChannels(
            (data.channels || []).map((c: { id: number; name: string }) => ({
              id: c.id,
              name: c.name,
            }))
          )
        }
      } catch {
        // Filter dropdown is non-critical; the list still works without it
      }
    }
    fetchChannels()
  }, [])

  const handleChannelFilterChange = (value: string) => {
    setChannelFilter(value)
    setPage(0)
  }

  const handleStatusFilterChange = (value: string) => {
    setStatusFilter(value)
    setPage(0)
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const rangeStart = total === 0 ? 0 : page * PAGE_SIZE + 1
  const rangeEnd = Math.min(total, (page + 1) * PAGE_SIZE)

  return (
    <div className="max-w-5xl mx-auto">
      <div className="bg-white rounded-lg shadow-md p-6">
        {/* Header row */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center">
            <HistoryIcon className="h-6 w-6 mr-2 text-red-600" />
            <h2 className="text-xl font-semibold text-gray-900">Download History</h2>
          </div>
          <button
            onClick={fetchDownloads}
            disabled={isLoading}
            className="inline-flex items-center px-3 py-2 rounded-md text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            <RefreshCwIcon className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4">
          <div>
            <label htmlFor="history-channel-filter" className="block text-sm font-medium text-gray-700 mb-1">
              Channel
            </label>
            <select
              id="history-channel-filter"
              value={channelFilter}
              onChange={(e) => handleChannelFilterChange(e.target.value)}
              className="block w-48 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-red-500 focus:ring-red-500"
            >
              <option value="">All channels</option>
              {channels.map((channel) => (
                <option key={channel.id} value={channel.id}>
                  {channel.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="history-status-filter" className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              id="history-status-filter"
              value={statusFilter}
              onChange={(e) => handleStatusFilterChange(e.target.value)}
              className="block w-44 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-red-500 focus:ring-red-500"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-start">
            <AlertCircleIcon className="h-5 w-5 text-red-500 mr-2 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {isLoading ? (
          <div className="py-12 text-center text-gray-500">
            <RefreshCwIcon className="h-8 w-8 mx-auto mb-3 animate-spin text-gray-400" />
            <p>Loading download history...</p>
          </div>
        ) : downloads.length === 0 && !error ? (
          /* Empty state */
          <div className="py-12 text-center text-gray-500">
            <HistoryIcon className="h-10 w-10 mx-auto mb-3 text-gray-300" />
            <p className="font-medium text-gray-700 mb-1">No downloads found</p>
            <p className="text-sm">
              {channelFilter || statusFilter
                ? 'Try adjusting the filters above.'
                : 'Downloads will appear here once your channels start downloading videos.'}
            </p>
          </div>
        ) : (
          <>
            {/* Downloads table */}
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Video
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Channel
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {downloads.map((download) => (
                    <tr key={download.id} className="hover:bg-gray-50">
                      <td className="px-3 py-3 max-w-md">
                        <div className="flex items-start">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate" title={download.title}>
                              {download.title}
                            </p>
                            <a
                              href={`https://www.youtube.com/watch?v=${download.video_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center text-xs text-gray-500 hover:text-red-600"
                            >
                              {download.video_id}
                              <ExternalLinkIcon className="h-3 w-3 ml-1" />
                            </a>
                            {download.status === 'failed' && download.error_message && (
                              <p className="text-xs text-red-600 mt-1 break-words" title={download.error_message}>
                                {download.error_message}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-700 whitespace-nowrap">
                        {download.channel_name || `Channel #${download.channel_id}`}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <StatusBadge
                          status={download.status}
                          fileExists={download.file_exists}
                          deletedAt={download.deleted_at}
                        />
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-700 whitespace-nowrap">
                        {formatFileSize(download.file_size)}
                      </td>
                      <td className="px-3 py-3 text-sm text-gray-700 whitespace-nowrap">
                        {formatDate(download.completed_at || download.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
              <p className="text-sm text-gray-600">
                Showing {rangeStart}–{rangeEnd} of {total}
              </p>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0 || isLoading}
                  className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
                >
                  <ChevronLeftIcon className="h-4 w-4 mr-1" />
                  Previous
                </button>
                <span className="text-sm text-gray-600">
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page + 1 >= totalPages || isLoading}
                  className="inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 transition-colors"
                >
                  Next
                  <ChevronRightIcon className="h-4 w-4 ml-1" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
