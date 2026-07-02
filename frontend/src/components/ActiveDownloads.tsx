import React, { useState, useEffect, useCallback } from 'react'
import { DownloadIcon, Loader2Icon } from 'lucide-react'

/**
 * ActiveDownloads - Live progress panel for in-flight downloads (US-010)
 *
 * Polls /api/v1/downloads/active every 2 seconds and renders a progress bar
 * per active download (title, channel, percent, speed, ETA). Renders nothing
 * when idle, so it costs no screen space outside download windows.
 *
 * Polling (not SSE) is deliberate: the Next.js pages-router API proxy
 * buffers streaming responses, and a 2s poll of an in-memory snapshot is
 * effectively real-time for a personal media server.
 */

interface ActiveDownload {
  video_id: string
  channel_id: number
  channel_name: string
  title: string
  status: string
  percent: number
  downloaded_bytes: number
  total_bytes?: number | null
  speed?: number | null
  eta_seconds?: number | null
}

const POLL_INTERVAL_MS = 2000

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function formatSpeed(bytesPerSecond?: number | null): string {
  if (!bytesPerSecond) return ''
  return `${formatBytes(bytesPerSecond)}/s`
}

function formatEta(seconds?: number | null): string {
  if (seconds == null || seconds < 0) return ''
  if (seconds < 60) return `${Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${Math.round(seconds % 60)}s`
}

export function ActiveDownloads() {
  const [downloads, setDownloads] = useState<ActiveDownload[]>([])

  const poll = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/downloads/active')
      if (response.ok) {
        const data = await response.json()
        setDownloads(data.active || [])
      }
    } catch {
      // Transient poll failures are invisible; next poll retries
    }
  }, [])

  useEffect(() => {
    poll()
    const interval = setInterval(poll, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [poll])

  if (downloads.length === 0) return null

  return (
    <div className="bg-white rounded-lg shadow-md p-5" data-testid="active-downloads">
      <div className="flex items-center mb-3">
        <DownloadIcon className="h-5 w-5 mr-2 text-red-600 animate-pulse" />
        <h3 className="font-semibold text-gray-900">
          Downloading ({downloads.length})
        </h3>
      </div>
      <div className="space-y-3">
        {downloads.map((download) => (
          <div key={download.video_id}>
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm font-medium text-gray-900 truncate mr-2" title={download.title}>
                {download.title}
              </p>
              <span className="text-xs text-gray-500 whitespace-nowrap">
                {download.status === 'processing' ? (
                  <span className="inline-flex items-center">
                    <Loader2Icon className="h-3 w-3 mr-1 animate-spin" />
                    Processing
                  </span>
                ) : (
                  `${download.percent.toFixed(0)}%`
                )}
              </span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2" role="progressbar"
              aria-valuenow={download.percent} aria-valuemin={0} aria-valuemax={100}
              aria-label={`Download progress for ${download.title}`}>
              <div
                className={`h-2 rounded-full transition-all ${download.status === 'processing' ? 'bg-yellow-500' : 'bg-red-600'}`}
                style={{ width: `${Math.min(100, download.percent)}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {download.channel_name}
              {download.total_bytes ? ` · ${formatBytes(download.downloaded_bytes)} of ${formatBytes(download.total_bytes)}` : ''}
              {download.speed ? ` · ${formatSpeed(download.speed)}` : ''}
              {download.eta_seconds != null ? ` · ${formatEta(download.eta_seconds)} left` : ''}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
