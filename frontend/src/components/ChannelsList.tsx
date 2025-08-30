import React, { useState, useRef, useEffect } from 'react'
import { YoutubeIcon, TrashIcon, CheckCircleIcon, EditIcon, CheckIcon, XIcon, RefreshCwIcon, AlertCircleIcon, HardDriveIcon, DownloadIcon } from 'lucide-react'

/**
 * ChannelsList Component - Displays and manages YouTube channels with inline limit editing
 * 
 * This component implements User Story 2: Configure Channel Video Limit
 * 
 * Features:
 * - Display channels in a scrollable list with metadata
 * - Inline editing of video limits with click-to-edit UI
 * - Input validation (1-100 range) with immediate feedback
 * - Confirmation dialog for significant limit reductions (>50% decrease)
 * - Optimistic UI updates with rollback on API errors
 * - Keyboard shortcuts (Enter to save, Escape to cancel)
 * - Real-time API integration with proper error handling
 * - YAML configuration sync via backend API
 * 
 * User Interactions:
 * 1. Click edit icon next to limit to start editing
 * 2. Use number input with +/- controls or type directly
 * 3. Press Enter to save or click checkmark
 * 4. Press Escape to cancel or click X
 * 5. Confirm significant reductions in modal dialog
 * 
 * Technical Details:
 * - Uses PUT /api/v1/channels/{id} to update limits
 * - Validates 1-100 range on frontend and backend
 * - Thread-safe YAML file updates via backend utils
 * - Prevents UI interaction during API calls
 * - Maintains edit state isolation per channel
 */

interface Channel {
  id: number
  url: string
  name: string
  limit: number
  enabled: boolean
  created_at: string
  updated_at: string
  metadata_status: string
  metadata_path?: string
  directory_path?: string
  last_metadata_update?: string
  cover_image_path?: string
  backdrop_image_path?: string
}

interface ChannelsListProps {
  channels: Channel[]
  selectedChannelId: number | null
  onSelectChannel: (channelId: number) => void
  onRemoveChannel: (channelId: number) => void
  onUpdateChannel?: (channelId: number, updates: Partial<Channel>) => void
}

export function ChannelsList({
  channels,
  selectedChannelId,
  onSelectChannel,
  onRemoveChannel,
  onUpdateChannel,
}: ChannelsListProps) {
  // === EDITING STATE MANAGEMENT ===
  // Controls which channel is currently being edited (null = no channel in edit mode)
  const [editingChannelId, setEditingChannelId] = useState<number | null>(null)
  
  // Current value in the edit input field (may differ from saved value during editing)
  const [editingLimit, setEditingLimit] = useState<number>(10)
  
  // Original limit value before editing started (used for reset/cancel and confirmation logic)
  const [originalLimit, setOriginalLimit] = useState<number>(10)
  
  // Loading state during API calls (prevents multiple simultaneous updates)
  const [isUpdating, setIsUpdating] = useState(false)
  
  // Error message to display when update fails (cleared on new edit attempts)
  const [updateError, setUpdateError] = useState<string>('')
  
  // === CONFIRMATION DIALOG STATE ===
  // Controls visibility of confirmation dialog for significant limit reductions
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  
  // Stores the pending update data while waiting for user confirmation
  const [pendingUpdate, setPendingUpdate] = useState<{channelId: number, newLimit: number} | null>(null)
  
  // Reference to the number input for programmatic focus and text selection
  const editInputRef = useRef<HTMLInputElement>(null)
  
  // === METADATA REFRESH STATE ===
  // Track which channel is currently having its metadata refreshed
  const [refreshingChannelId, setRefreshingChannelId] = useState<number | null>(null)
  const [refreshError, setRefreshError] = useState<string>('')

  // === DOWNLOAD STATE ===
  // Track which channel is currently downloading videos
  const [downloadingChannelId, setDownloadingChannelId] = useState<number | null>(null)
  const [downloadError, setDownloadError] = useState<string>('')
  const [downloadSuccess, setDownloadSuccess] = useState<string>('')

  if (!channels || channels.length === 0) {
    return null
  }

  // === UX ENHANCEMENT: AUTO-SELECT TEXT ===
  // When a channel enters edit mode, automatically select all text in the input
  // This allows users to immediately type new values (e.g., "9") to replace old ones (e.g., "10")
  // without having to manually select or delete existing digits
  useEffect(() => {
    if (editingChannelId && editInputRef.current) {
      // Small delay ensures the input element is fully rendered and accessible
      // This prevents race conditions where we try to manipulate the input before it exists
      const timer = setTimeout(() => {
        if (editInputRef.current) {
          editInputRef.current.focus()    // Ensure input has focus
          editInputRef.current.select()   // Select all text for easy replacement
        }
      }, 10)
      
      // Cleanup timer if component unmounts or editingChannelId changes
      return () => clearTimeout(timer)
    }
  }, [editingChannelId]) // Re-run whenever the editing channel changes

  // === EVENT HANDLERS ===
  
  /**
   * Initiates edit mode for a channel's video limit
   * Can be triggered by clicking the limit text or edit icon
   */
  const startEditingLimit = (channel: Channel, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent channel selection when clicking edit controls
    
    // Initialize edit state with current channel values
    setEditingChannelId(channel.id)      // Mark this channel as being edited
    setEditingLimit(channel.limit)       // Set input value to current limit
    setOriginalLimit(channel.limit)      // Store original for reset/cancel functionality
    setUpdateError('')                   // Clear any previous error messages
  }

  /**
   * Cancels edit mode and resets all editing state
   * Triggered by Escape key, cancel button, or clicking outside edit area
   */
  const cancelEditingLimit = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation() // Prevent event bubbling if triggered by button click
    
    // Reset all editing state to pre-edit values
    setEditingChannelId(null)            // Exit edit mode
    setUpdateError('')                   // Clear error messages
    setEditingLimit(originalLimit)       // Restore original limit value in case user changed it
  }

  /**
   * Confirms a pending limit update after user approves the confirmation dialog
   * Used for significant limit reductions that require user confirmation
   */
  const confirmLimitUpdate = () => {
    if (pendingUpdate) {
      // Execute the pending update that was waiting for confirmation
      performLimitUpdate(pendingUpdate.channelId, pendingUpdate.newLimit)
      
      // Clean up confirmation dialog state
      setShowConfirmDialog(false)
      setPendingUpdate(null)
    }
  }

  /**
   * Cancels a pending limit update and closes the confirmation dialog
   * User decided not to proceed with the significant reduction
   */
  const cancelConfirmDialog = () => {
    // Hide confirmation dialog and clear pending update
    setShowConfirmDialog(false)
    setPendingUpdate(null)
    
    // Reset the input field to original value since user cancelled the change
    setEditingLimit(originalLimit)
  }

  /**
   * Validates and saves the edited limit value
   * Handles confirmation dialog for significant reductions and immediate updates for small changes
   * Triggered by Enter key, save button click, or programmatic calls
   */
  const saveLimit = async (channelId: number, e?: React.MouseEvent) => {
    if (e) e.stopPropagation() // Prevent event bubbling if called from button click
    
    // === INPUT VALIDATION ===
    // Frontend validation to catch invalid ranges before API call
    if (editingLimit < 1 || editingLimit > 100) {
      setUpdateError('Limit must be between 1 and 100')
      return // Stop here - don't proceed with invalid values
    }

    // === CONFIRMATION LOGIC FOR SIGNIFICANT REDUCTIONS ===
    // Calculate percentage reduction to determine if confirmation is needed
    const reductionPercentage = ((originalLimit - editingLimit) / originalLimit) * 100
    
    // Show confirmation dialog for reductions >50% on limits >10
    // This prevents accidental data loss from mistaken large reductions
    if (reductionPercentage > 50 && originalLimit > 10) {
      // Store the update details for later execution after user confirms
      setPendingUpdate({ channelId, newLimit: editingLimit })
      setShowConfirmDialog(true)
      return // Wait for user confirmation before proceeding
    }

    // === IMMEDIATE UPDATE FOR SMALL CHANGES ===
    // For small changes or increases, proceed immediately without confirmation
    performLimitUpdate(channelId, editingLimit)
  }

  /**
   * Performs the actual API call to update the channel limit
   * This function handles the HTTP request, optimistic UI updates, and error handling
   * Called after validation and any necessary user confirmations
   */
  const performLimitUpdate = async (channelId: number, newLimit: number) => {
    // Set loading state to prevent multiple simultaneous updates
    setIsUpdating(true)
    setUpdateError('') // Clear any previous errors

    try {
      // === API CALL ===
      // Send PUT request to update channel limit
      // Backend will validate, update database, and sync to YAML config
      const response = await fetch(`/api/v1/channels/${channelId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          limit: newLimit, // Only sending the limit field for partial update
        }),
      })

      if (response.ok) {
        // === SUCCESS HANDLING ===
        const updatedChannel = await response.json()
        
        // Update parent component's state with new limit (optimistic update)
        if (onUpdateChannel) {
          onUpdateChannel(channelId, { limit: newLimit })
        }
        
        // Exit edit mode on successful update
        setEditingChannelId(null)
      } else {
        // === ERROR HANDLING ===
        // Parse error response from API (usually validation errors)
        const errorData = await response.json()
        setUpdateError(errorData.detail || 'Failed to update limit')
      }
    } catch (error) {
      // === NETWORK ERROR HANDLING ===
      // Handle network failures, server unavailable, etc.
      console.error('Error updating channel limit:', error)
      setUpdateError('Network error: Failed to update limit')
    } finally {
      // Always clear loading state, regardless of success or failure
      setIsUpdating(false)
    }
  }

  /**
   * Handles keyboard shortcuts for the edit input field
   * Enter: Save changes, Escape: Cancel editing
   */
  const handleKeyPress = (e: React.KeyboardEvent, channelId: number) => {
    if (e.key === 'Enter') {
      saveLimit(channelId) // Trigger save with validation and confirmation logic
    } else if (e.key === 'Escape') {
      cancelEditingLimit() // Cancel editing and reset to original value
    }
  }

  /**
   * Refreshes channel metadata including directory structure and images
   */
  const refreshChannelMetadata = async (channelId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    
    setRefreshingChannelId(channelId)
    setRefreshError('')
    
    try {
      const response = await fetch(`/api/v1/channels/${channelId}/refresh-metadata`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const result = await response.json()
        
        // Update parent component to refresh channel data
        if (onUpdateChannel) {
          // Trigger a full refresh of channels list
          window.location.reload() // Simple approach for now
        }
        
        if (result.warnings && result.warnings.length > 0) {
          setRefreshError(`Refreshed with warnings: ${result.warnings.join(', ')}`)
        }
      } else {
        const errorData = await response.json()
        setRefreshError(errorData.detail || 'Failed to refresh metadata')
      }
    } catch (error) {
      console.error('Error refreshing channel metadata:', error)
      setRefreshError('Network error: Failed to refresh metadata')
    } finally {
      setRefreshingChannelId(null)
    }
  }

  /**
   * Triggers video download for a channel
   */
  const downloadChannelVideos = async (channelId: number, e: React.MouseEvent) => {
    e.stopPropagation()
    
    setDownloadingChannelId(channelId)
    setDownloadError('')
    setDownloadSuccess('')
    
    try {
      const response = await fetch(`/api/v1/channels/${channelId}/download`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        const result = await response.json()
        
        if (result.success) {
          const count = result.videos_downloaded
          if (count > 0) {
            setDownloadSuccess(`Successfully downloaded ${count} video${count === 1 ? '' : 's'}`)
          } else {
            setDownloadSuccess('No new videos to download')
          }
        } else {
          setDownloadError(result.error_message || 'Download failed')
        }
      } else {
        const errorData = await response.json().catch(() => ({}))
        setDownloadError(`Failed to start download: ${errorData.detail || 'Unknown error'}`)
      }
    } catch (error) {
      console.error('Download error:', error)
      setDownloadError('Network error while starting download')
    } finally {
      setDownloadingChannelId(null)
      
      // Clear success/error messages after a delay
      setTimeout(() => {
        setDownloadSuccess('')
        setDownloadError('')
      }, 5000)
    }
  }

  /**
   * Get metadata status icon and color based on status
   */
  const getMetadataStatusIcon = (status: string, isRefreshing: boolean = false) => {
    if (isRefreshing) {
      return <RefreshCwIcon className="h-3 w-3 text-blue-600 animate-spin" />
    }
    
    switch (status) {
      case 'completed':
        return <HardDriveIcon className="h-3 w-3 text-green-600" />
      case 'failed':
        return <AlertCircleIcon className="h-3 w-3 text-red-600" />
      case 'refreshing':
        return <RefreshCwIcon className="h-3 w-3 text-blue-600 animate-spin" />
      case 'pending':
      default:
        return <HardDriveIcon className="h-3 w-3 text-gray-400" />
    }
  }

  /**
   * Get metadata status text and tooltip
   */
  const getMetadataStatusText = (channel: Channel) => {
    const { metadata_status, last_metadata_update } = channel
    const lastUpdate = last_metadata_update ? new Date(last_metadata_update).toLocaleDateString() : 'Never'
    
    switch (metadata_status) {
      case 'completed':
        return { text: `Metadata ready (${lastUpdate})`, color: 'text-green-600' }
      case 'failed':
        return { text: `Metadata failed (${lastUpdate})`, color: 'text-red-600' }
      case 'refreshing':
        return { text: 'Refreshing metadata...', color: 'text-blue-600' }
      case 'pending':
      default:
        return { text: 'Metadata pending', color: 'text-gray-500' }
    }
  }

  return (
    <div>
      <h3 className="text-lg font-medium mb-4">Your Channels</h3>
      
      {/* === CHANNEL LIST CONTAINER === */}
      <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
        {channels.map((channel) => (
          <div
            key={channel.id}
            className={`flex items-center justify-between border rounded-lg p-3 hover:bg-gray-50 cursor-pointer ${
              selectedChannelId === channel.id ? 'border-red-500 bg-red-50' : 'border-gray-200'  // Selected state
            } ${editingChannelId === channel.id ? 'border-blue-500 bg-blue-50' : ''}`}           // Editing state
            onClick={() => editingChannelId !== channel.id && onSelectChannel(channel.id)}      // Prevent selection during edit
          >
            <div className="flex items-center flex-grow min-w-0">
              <YoutubeIcon className="h-5 w-5 text-red-600 mr-3 flex-shrink-0" />
              <div className="min-w-0">
                <h4 className="text-sm font-medium text-gray-900 truncate">
                  {channel.name}
                </h4>
                <p className="text-xs text-gray-500 truncate mt-0.5">
                  {channel.url}
                </p>
                {/* Metadata status indicator */}
                <div className="flex items-center mt-1">
                  {getMetadataStatusIcon(channel.metadata_status, refreshingChannelId === channel.id)}
                  <span className={`text-xs ml-1 ${getMetadataStatusText(channel).color}`}>
                    {getMetadataStatusText(channel).text}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center ml-4">
              {/* === CONDITIONAL RENDERING: EDIT MODE vs VIEW MODE === */}
              {editingChannelId === channel.id ? (
                // === EDIT MODE UI ===
                <div className="flex items-center space-x-2" onClick={(e) => e.stopPropagation()}>
                  <div className="flex flex-col">
                    <div className="flex items-center space-x-1">
                      {/* Number input with auto-select functionality */}
                      <input
                        ref={editInputRef}                                              // Ref for programmatic focus/select
                        type="number"
                        min="1"
                        max="100"
                        value={editingLimit}
                        onChange={(e) => setEditingLimit(parseInt(e.target.value) || 1)}
                        onKeyDown={(e) => handleKeyPress(e, channel.id)}                // Enter/Escape shortcuts
                        onFocus={(e) => e.target.select()}                             // Fallback text selection
                        className="w-16 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        disabled={isUpdating}                                          // Prevent changes during API call
                      />
                      
                      {/* Save button (green checkmark) */}
                      <button
                        onClick={(e) => saveLimit(channel.id, e)}
                        disabled={isUpdating}
                        className="text-green-600 hover:text-green-700 disabled:text-gray-400 p-1"
                        title="Save (Enter)"
                      >
                        <CheckIcon className="h-3 w-3" />
                      </button>
                      
                      {/* Cancel button (gray X) */}
                      <button
                        onClick={cancelEditingLimit}
                        disabled={isUpdating}
                        className="text-gray-600 hover:text-gray-700 disabled:text-gray-400 p-1"
                        title="Cancel (Escape)"
                      >
                        <XIcon className="h-3 w-3" />
                      </button>
                    </div>
                    
                    {/* Error message display */}
                    {updateError && (
                      <span className="text-xs text-red-500 mt-1">{updateError}</span>
                    )}
                  </div>
                </div>
              ) : (
                // === VIEW MODE UI ===
                <div className="flex items-center space-x-2">
                  {/* Clickable limit display - UX enhancement for easier editing */}
                  <button
                    onClick={(e) => startEditingLimit(channel, e)}
                    className="text-xs text-gray-600 hover:text-blue-600 hover:underline cursor-pointer"
                    title="Click to edit limit"
                  >
                    Limit: {channel.limit}
                  </button>
                  
                  {/* Traditional edit icon - alternative way to start editing */}
                  <button
                    onClick={(e) => startEditingLimit(channel, e)}
                    className="text-gray-400 hover:text-blue-600 p-1"
                    title="Edit limit"
                  >
                    <EditIcon className="h-3 w-3" />
                  </button>
                  
                  {/* Refresh metadata button */}
                  <button
                    onClick={(e) => refreshChannelMetadata(channel.id, e)}
                    disabled={refreshingChannelId === channel.id}
                    className="text-gray-400 hover:text-blue-600 p-1 disabled:text-gray-300"
                    title="Refresh metadata"
                  >
                    <RefreshCwIcon className={`h-3 w-3 ${refreshingChannelId === channel.id ? 'animate-spin' : ''}`} />
                  </button>
                  
                  {/* Download videos button */}
                  <button
                    onClick={(e) => downloadChannelVideos(channel.id, e)}
                    disabled={downloadingChannelId === channel.id || !channel.enabled}
                    className="text-gray-400 hover:text-green-600 p-1 disabled:text-gray-300"
                    title={!channel.enabled ? "Channel disabled" : "Download recent videos"}
                  >
                    <DownloadIcon className={`h-3 w-3 ${downloadingChannelId === channel.id ? 'animate-pulse' : ''}`} />
                  </button>
                </div>
              )}
              
              {selectedChannelId === channel.id && editingChannelId !== channel.id && (
                <CheckCircleIcon className="h-4 w-4 text-green-600 mr-2" />
              )}
              
              <button
                className="text-gray-400 hover:text-red-600 p-1 ml-2"
                onClick={(e) => {
                  e.stopPropagation()
                  onRemoveChannel(channel.id)
                }}
                title="Remove channel"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* === REFRESH ERROR DISPLAY === */}
      {refreshError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center">
            <AlertCircleIcon className="h-4 w-4 text-red-600 mr-2" />
            <span className="text-sm text-red-700">{refreshError}</span>
            <button
              onClick={() => setRefreshError('')}
              className="ml-auto text-red-600 hover:text-red-700"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* === DOWNLOAD SUCCESS DISPLAY === */}
      {downloadSuccess && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center">
            <CheckCircleIcon className="h-4 w-4 text-green-600 mr-2" />
            <span className="text-sm text-green-700">{downloadSuccess}</span>
            <button
              onClick={() => setDownloadSuccess('')}
              className="ml-auto text-green-600 hover:text-green-700"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* === DOWNLOAD ERROR DISPLAY === */}
      {downloadError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center">
            <AlertCircleIcon className="h-4 w-4 text-red-600 mr-2" />
            <span className="text-sm text-red-700">{downloadError}</span>
            <button
              onClick={() => setDownloadError('')}
              className="ml-auto text-red-600 hover:text-red-700"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* === CONFIRMATION DIALOG FOR SIGNIFICANT LIMIT REDUCTIONS === */}
      {/* Only shown when user attempts to reduce limit by >50% on channels with limit >10 */}
      {showConfirmDialog && pendingUpdate && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md mx-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Confirm Limit Reduction
            </h3>
            
            {/* Clear explanation of what's about to happen */}
            <p className="text-sm text-gray-600 mb-4">
              You're reducing the video limit from <strong>{originalLimit}</strong> to{' '}
              <strong>{pendingUpdate.newLimit}</strong>. This is a significant reduction
              that will affect future downloads.
            </p>
            
            {/* Important note about existing videos */}
            <p className="text-xs text-gray-500 mb-6">
              Note: Existing videos beyond the new limit won't be deleted immediately,
              but future downloads will respect the new limit.
            </p>
            
            {/* Action buttons */}
            <div className="flex space-x-3">
              {/* Confirm button (red to indicate significant action) */}
              <button
                onClick={confirmLimitUpdate}
                disabled={isUpdating}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md text-sm font-medium disabled:bg-red-400"
              >
                {isUpdating ? 'Updating...' : 'Confirm'}
              </button>
              
              {/* Cancel button (safe option) */}
              <button
                onClick={cancelConfirmDialog}
                disabled={isUpdating}
                className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 px-4 py-2 rounded-md text-sm font-medium disabled:bg-gray-200"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}