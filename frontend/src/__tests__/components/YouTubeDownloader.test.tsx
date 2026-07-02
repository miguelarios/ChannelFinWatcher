import React from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { YouTubeDownloader } from '../../components/YouTubeDownloader'

/**
 * YouTubeDownloader Component Tests
 * 
 * Tests the core functionality of User Story 1: Add Channel via Web UI
 * These tests focus on the essential acceptance criteria from Story 1:
 * - Valid YouTube channel addition (Happy Path)
 * - Form validation for invalid inputs
 * - Multiple channel addition capability
 */

// Mock fetch globally for API testing
global.fetch = jest.fn()

// Stub out SchedulerStatusWidget: it fires its own fetches on mount
// (/scheduler/status, /channels) which would consume the ordered fetch
// mocks below and break every assertion that depends on call order.
jest.mock('../../components/SchedulerStatusWidget', () => ({
  SchedulerStatusWidget: () => null,
}))

const jsonResponse = (body: unknown, ok = true) => ({ ok, json: () => Promise.resolve(body) })

// Responses for POST /api/v1/channels, consumed in order. Tests push what
// they need. URL-dispatched mocking (instead of ordered mockResolvedValueOnce
// chains) keeps tests immune to changes in how many fetches mount performs.
let postChannelResponses: unknown[] = []

describe('YouTubeDownloader Component - Story 1 Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    postChannelResponses = []
    ;(fetch as jest.Mock).mockReset()
    ;(fetch as jest.Mock).mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/health') {
        return Promise.resolve(jsonResponse({ status: 'healthy' }))
      }
      if (url === '/api/v1/settings/default-video-limit') {
        return Promise.resolve(jsonResponse({ limit: 10 }))
      }
      if (url === '/api/v1/channels' && options?.method === 'POST') {
        const next = postChannelResponses.shift()
        if (next instanceof Promise) return next
        return Promise.resolve(next ?? jsonResponse({ detail: 'No mocked POST response queued' }, false))
      }
      if (url === '/api/v1/channels') {
        return Promise.resolve(jsonResponse({ channels: [], total: 0, enabled: 0 }))
      }
      return Promise.resolve(jsonResponse({}))
    })
  })

  describe('Form Rendering - Story 1 Requirements', () => {
    it('renders the Add New Channel form with required fields', async () => {
      render(<YouTubeDownloader />)

      // Wait for component initialization
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /add youtube channels for monitoring/i })).toBeInTheDocument()
      })

      // Verify form elements from Story 1 acceptance criteria
      expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      expect(screen.getByPlaceholderText('https://www.youtube.com/@ChannelName')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /add channel for monitoring/i })).toBeInTheDocument()
      
      // Video limit selection should be present
      const radioButtons = screen.getAllByRole('radio')
      expect(radioButtons).toHaveLength(2) // Default and custom options
      expect(radioButtons[0]).toBeChecked() // Default selected initially
    })

    it('displays form with proper labels and structure', async () => {
      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByText('Add New Channel')).toBeInTheDocument()
      })

      expect(screen.getByText(/number of recent videos to keep/i)).toBeInTheDocument()
      expect(screen.getByText(/use default.*videos/i)).toBeInTheDocument()
    })
  })

  describe('Story 1 Scenario: Add Valid YouTube Channel - Happy Path', () => {
    it('successfully adds a valid YouTube channel with default limit', async () => {
      const user = userEvent.setup()
      
      // Mock successful channel creation
      postChannelResponses.push(jsonResponse({
        id: 1,
        url: 'https://www.youtube.com/@MrsRachel',
        name: 'Mrs. Rachel - Toddler Learning Videos',
        limit: 10,
        enabled: true,
        metadata_status: 'completed',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      }))

      render(<YouTubeDownloader />)

      // Wait for initialization
      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      // Enter valid YouTube URL
      const urlInput = screen.getByRole('textbox', { name: /youtube channel url/i })
      await act(async () => {
        await user.type(urlInput, 'https://www.youtube.com/@MrsRachel')
      })

      // Submit form
      const submitButton = screen.getByRole('button', { name: /add channel for monitoring/i })
      await act(async () => {
        await user.click(submitButton)
      })

      // Wait for success state
      await waitFor(() => {
        expect(screen.getByText(/successfully added channel/i)).toBeInTheDocument()
      }, { timeout: 3000 })

      // Verify API call was made correctly. quality_preset is intentionally
      // omitted so the backend applies the global default quality (US-015),
      // and no limit field means the default video limit applies (US-003)
      expect(fetch).toHaveBeenCalledWith('/api/v1/channels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: 'https://www.youtube.com/@MrsRachel',
          enabled: true
        }),
      })

      // Verify form clears after successful submission
      expect(urlInput).toHaveValue('')

      // Verify new channel card appears (Story 1 requirement)
      await waitFor(() => {
        expect(screen.getByText('Mrs. Rachel - Toddler Learning Videos')).toBeInTheDocument()
      })
    })

    it('displays channel information in card format', async () => {
      const user = userEvent.setup()
      
      postChannelResponses.push(jsonResponse({
        id: 1,
        name: 'Test Channel',
        url: 'https://www.youtube.com/@TestChannel',
        limit: 10,
        enabled: true,
        metadata_status: 'completed',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z'
      }))

      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      const urlInput = screen.getByRole('textbox', { name: /youtube channel url/i })
      await act(async () => {
        await user.type(urlInput, 'https://www.youtube.com/@TestChannel')
      })

      await act(async () => {
        await user.click(screen.getByRole('button', { name: /add channel for monitoring/i }))
      })

      // Channel card should display channel name, URL, and video limit (Story 1 requirement)
      await waitFor(() => {
        expect(screen.getByText('Test Channel')).toBeInTheDocument()
        expect(screen.getByText('Limit: 10')).toBeInTheDocument()
      })
    })
  })

  describe('Story 1 Scenario: Form Validation - Invalid Inputs', () => {
    it('shows error when URL field is empty', async () => {
      const user = userEvent.setup()
      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add channel for monitoring/i })).toBeInTheDocument()
      })

      // Submit form without entering URL
      await act(async () => {
        await user.click(screen.getByRole('button', { name: /add channel for monitoring/i }))
      })

      // Should show validation error
      expect(screen.getByText('Please enter a YouTube channel URL')).toBeInTheDocument()
      
      // Should not make API call for channel creation
      const channelAPICalls = (fetch as jest.Mock).mock.calls.filter(call => 
        call[0] === '/api/v1/channels' && call[1]?.method === 'POST'
      )
      expect(channelAPICalls).toHaveLength(0)
    })

    it('shows error for invalid URL format', async () => {
      const user = userEvent.setup()
      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      // Enter invalid URL
      const urlInput = screen.getByRole('textbox', { name: /youtube channel url/i })
      await act(async () => {
        await user.type(urlInput, 'not-a-youtube-url')
      })

      await act(async () => {
        await user.click(screen.getByRole('button', { name: /add channel for monitoring/i }))
      })

      expect(screen.getByText('Please enter a valid YouTube channel URL')).toBeInTheDocument()
      
      // Should not make API call
      const channelAPICalls = (fetch as jest.Mock).mock.calls.filter(call => 
        call[0] === '/api/v1/channels' && call[1]?.method === 'POST'
      )
      expect(channelAPICalls).toHaveLength(0)
    })

    it('applies error styling to invalid inputs', async () => {
      const user = userEvent.setup()
      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      const urlInput = screen.getByRole('textbox', { name: /youtube channel url/i })
      
      // Submit empty form to trigger validation
      await act(async () => {
        await user.click(screen.getByRole('button', { name: /add channel for monitoring/i }))
      })

      // Input should have error styling
      expect(urlInput).toHaveClass('border-red-500')
    })
  })

  describe('Story 1 Scenario: Multiple Channel Addition', () => {
    it('allows multiple channels to be added sequentially', async () => {
      const user = userEvent.setup()
      
      // Mock responses for multiple channel additions
      postChannelResponses.push(
        jsonResponse({
          id: 1,
          name: 'First Channel',
          url: 'https://www.youtube.com/@FirstChannel',
          limit: 10,
          enabled: true,
          metadata_status: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        }),
        jsonResponse({
          id: 2,
          name: 'Second Channel',
          url: 'https://www.youtube.com/@SecondChannel',
          limit: 10,
          enabled: true,
          metadata_status: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        })
      )

      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      const urlInput = screen.getByRole('textbox', { name: /youtube channel url/i })
      const submitButton = screen.getByRole('button', { name: /add channel for monitoring/i })

      // Add first channel
      await act(async () => {
        await user.type(urlInput, 'https://www.youtube.com/@FirstChannel')
        await user.click(submitButton)
      })

      await waitFor(() => {
        expect(screen.getByText('First Channel')).toBeInTheDocument()
      })

      // Form should be cleared
      expect(urlInput).toHaveValue('')

      // Add second channel
      await act(async () => {
        await user.type(urlInput, 'https://www.youtube.com/@SecondChannel')
        await user.click(submitButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Second Channel')).toBeInTheDocument()
      })

      // Both channels should be visible (Story 1 requirement)
      expect(screen.getByText('First Channel')).toBeInTheDocument()
      expect(screen.getByText('Second Channel')).toBeInTheDocument()
    })
  })

  describe('Loading and Error States', () => {
    it('shows loading state during form submission', async () => {
      const user = userEvent.setup()
      
      // Mock slow API response
      let resolveChannelCreation: (value: any) => void
      const slowPromise = new Promise(resolve => {
        resolveChannelCreation = resolve
      })

      postChannelResponses.push(slowPromise.then(() => ({
        ok: true,
        json: () => Promise.resolve({
          id: 1,
          name: 'Test Channel',
          url: 'https://www.youtube.com/@TestChannel',
          limit: 10,
          enabled: true,
          metadata_status: 'completed',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z'
        })
      })))

      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      await act(async () => {
        await user.type(screen.getByRole('textbox', { name: /youtube channel url/i }), 'https://www.youtube.com/@TestChannel')
      })
      
      const submitButton = screen.getByRole('button', { name: /add channel for monitoring/i })
      
      await act(async () => {
        await user.click(submitButton)
      })

      // Should show loading state
      expect(screen.getByText('Adding Channel...')).toBeInTheDocument()
      expect(submitButton).toBeDisabled()

      // Resolve the promise to complete the test
      act(() => {
        resolveChannelCreation({})
      })
    })

    it('handles API errors gracefully', async () => {
      const user = userEvent.setup()
      
      // API error response for the POST
      postChannelResponses.push(jsonResponse({ detail: 'Channel not found' }, false))

      render(<YouTubeDownloader />)

      await waitFor(() => {
        expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toBeInTheDocument()
      })

      await act(async () => {
        await user.type(screen.getByRole('textbox', { name: /youtube channel url/i }), 'https://www.youtube.com/@BadChannel')
        await user.click(screen.getByRole('button', { name: /add channel for monitoring/i }))
      })

      await waitFor(() => {
        expect(screen.getByText('Channel not found')).toBeInTheDocument()
      })

      // Form should not clear on error
      expect(screen.getByRole('textbox', { name: /youtube channel url/i })).toHaveValue('https://www.youtube.com/@BadChannel')
    })
  })
})