import React, { useState, useEffect } from 'react'
import {
  AlertCircleIcon,
  PlusIcon,
} from 'lucide-react'
import { DownloadResults } from './DownloadResults'
import { ChannelsList } from './ChannelsList'

/**
 * Channel interface representing a YouTube channel configuration
 */
interface Channel {
  id: number
  url: string
  name: string
  limit: number
  enabled: boolean
  created_at: string
  updated_at: string
}

/**
 * Main component for adding and managing YouTube channels for monitoring.
 * 
 * This component implements Story 1: Add Channel via Web UI
 * - Provides form for entering YouTube channel URLs
 * - Validates input and calls backend API for channel creation
 * - Displays existing channels in card format
 * - Handles duplicate channel detection and error messaging
 * 
 * Key Features:
 * - Multiple YouTube URL format support (/@handle, /channel/UC..., etc.)
 * - Real-time form validation
 * - Loading states during API calls
 * - Channel list management (add/remove)
 * - Error handling with user-friendly messages
 */
export function YouTubeDownloader() {
  const [channelUrl, setChannelUrl] = useState('')
  const [videoCount, setVideoCount] = useState(10)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [hasSubmitted, setHasSubmitted] = useState(false)
  const [channels, setChannels] = useState<Channel[]>([])
  const [selectedChannelId, setSelectedChannelId] = useState<number | null>(null)

  /**
   * Client-side URL validation for basic YouTube URL format checking.
   * Note: More comprehensive validation happens on the backend via yt-dlp.
   * 
   * @param url - The URL to validate
   * @returns true if URL appears to be a YouTube URL
   */
  const isValidYouTubeUrl = (url: string) => {
    return url.includes('youtube.com/@') || 
           url.includes('youtube.com/channel/') || 
           url.includes('youtube.com/c/') ||
           url.includes('youtube.com/user/') ||
           url.includes('youtu.be')
  }

  // Load existing channels when component mounts
  useEffect(() => {
    loadChannels()
  }, [])

  /**
   * Load existing channels from the backend on component initialization.
   * First checks if backend is healthy, then fetches channel list.
   */
  const loadChannels = async () => {
    try {
      // First check if backend is available
      const response = await fetch('/api/health')
      const healthData = await response.json()
      
      if (healthData.status === 'healthy') {
        // Backend is available, fetch existing channels
        const channelsResponse = await fetch('/api/v1/channels')
        if (channelsResponse.ok) {
          const channelsData = await channelsResponse.json()
          setChannels(channelsData.channels || [])
        }
      }
    } catch (error) {
      console.error('Failed to load channels:', error)
      // Fail silently on initial load - user can still add channels
    }
  }

  /**
   * Handle form submission for adding a new YouTube channel.
   * 
   * Workflow:
   * 1. Validate form inputs (URL format, required fields)
   * 2. Check for client-side duplicates (basic URL comparison)
   * 3. Call backend API to extract channel metadata and store
   * 4. Update UI with new channel or display error message
   * 
   * @param e - Form submission event
   */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setHasSubmitted(true)

    // Basic form validation
    if (!channelUrl) {
      setError('Please enter a YouTube channel URL')
      return
    }

    if (!isValidYouTubeUrl(channelUrl)) {
      setError('Please enter a valid YouTube channel URL')
      return
    }

    // Client-side duplicate check (basic URL comparison)
    // Note: Backend does more thorough duplicate checking via channel_id
    const channelExists = channels.some((channel) => 
      channel.url.toLowerCase() === channelUrl.toLowerCase()
    )
    if (channelExists) {
      setError('This channel has already been added')
      return
    }

    setIsLoading(true)

    try {
      // Call backend API to add channel
      const response = await fetch('/api/v1/channels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: channelUrl,
          limit: videoCount,
          enabled: true,
          quality_preset: 'best'
        }),
      })

      if (response.ok) {
        // Channel successfully added
        const newChannel = await response.json()
        setChannels(prevChannels => [...prevChannels, newChannel])
        setSelectedChannelId(newChannel.id)
        setChannelUrl('') // Clear form
        setSuccess(`Successfully added channel: ${newChannel.name}`)
        
        // Auto-hide success message after 5 seconds
        setTimeout(() => {
          setSuccess('')
        }, 5000)
      } else {
        // Handle API error responses
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to add channel')
      }
    } catch (error) {
      console.error('Error adding channel:', error)
      setError('Network error: Failed to connect to server')
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectChannel = (channelId: number) => {
    setSelectedChannelId(channelId)
  }

  const handleRemoveChannel = async (channelId: number) => {
    try {
      const response = await fetch(`/api/v1/channels/${channelId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        setChannels(prevChannels => 
          prevChannels.filter(channel => channel.id !== channelId)
        )
        if (selectedChannelId === channelId) {
          setSelectedChannelId(null)
        }
      } else {
        setError('Failed to remove channel')
      }
    } catch (error) {
      console.error('Error removing channel:', error)
      setError('Network error: Failed to remove channel')
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6 max-w-3xl mx-auto">
      <h2 className="text-xl font-semibold mb-6">
        Add YouTube Channels for Monitoring
      </h2>
      
      <form onSubmit={handleSubmit} className="space-y-4 mb-8">
        <h3 className="text-lg font-medium mb-4">Add New Channel</h3>
        
        <div>
          <label
            htmlFor="channel-url"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            YouTube Channel URL
          </label>
          <input
            id="channel-url"
            type="text"
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            placeholder="https://www.youtube.com/@ChannelName"
            className={`w-full px-4 py-2 border rounded-md focus:ring-2 focus:ring-red-500 focus:outline-none ${
              hasSubmitted && (!channelUrl || !isValidYouTubeUrl(channelUrl)) 
                ? 'border-red-500' 
                : 'border-gray-300'
            }`}
          />
        </div>

        <div>
          <label
            htmlFor="video-count"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Number of Recent Videos to Keep
          </label>
          <input
            id="video-count"
            type="number"
            min="1"
            max="100"
            value={videoCount}
            onChange={(e) => setVideoCount(parseInt(e.target.value))}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-red-500 focus:outline-none"
          />
        </div>

        {error && (
          <div className="flex items-center text-red-500 text-sm">
            <AlertCircleIcon className="h-4 w-4 mr-1" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center text-green-600 text-sm">
            <span>{success}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-4 rounded-md transition duration-200 flex items-center justify-center disabled:bg-red-400"
        >
          {isLoading ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Adding Channel...
            </>
          ) : (
            <>
              <PlusIcon className="mr-2 h-5 w-5" />
              Add Channel for Monitoring
            </>
          )}
        </button>
      </form>

      {channels.length > 0 && (
        <div className="mb-8 border-t pt-6">
          <ChannelsList
            channels={channels}
            selectedChannelId={selectedChannelId}
            onSelectChannel={handleSelectChannel}
            onRemoveChannel={handleRemoveChannel}
          />
        </div>
      )}

      {/* Note: For Story 1, we only show channel addition success, not actual video downloads */}
      {isLoading && (
        <div className="mt-8">
          <DownloadResults isLoading={true} videos={[]} />
        </div>
      )}
    </div>
  )
}