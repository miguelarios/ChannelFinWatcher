import React, { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle, Info } from 'lucide-react'

interface DefaultVideoLimitSettings {
  limit: number
  description: string
  updated_at: string
}

export function Settings() {
  const [defaultLimit, setDefaultLimit] = useState<number>(10)
  const [originalLimit, setOriginalLimit] = useState<number>(10)
  const [loading, setLoading] = useState<boolean>(true)
  const [saving, setSaving] = useState<boolean>(false)
  const [error, setError] = useState<string>('')
  const [success, setSuccess] = useState<string>('')
  const [lastUpdated, setLastUpdated] = useState<string>('')

  // Fetch current default video limit setting
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

  // Save updated default video limit
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

  // Load settings on component mount
  useEffect(() => {
    fetchDefaultLimit()
  }, [])

  // Handle input change with validation
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
      </div>
    </div>
  )
}