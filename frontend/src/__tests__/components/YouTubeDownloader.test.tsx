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

describe('YouTubeDownloader Component - Story 1 Tests', () => {
  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks()
    ;(fetch as jest.Mock).mockClear()
    
    // Mock the default API calls that occur on component mount
    ;(fetch as jest.Mock)
      .mockResolvedValueOnce({
        // Health check
        ok: true,
        json: () => Promise.resolve({ status: 'healthy' })
      })
      .mockResolvedValueOnce({
        // Existing channels list (empty by default)
        ok: true,
        json: () => Promise.resolve({ channels: [], total: 0, enabled: 0 })
      })
      .mockResolvedValueOnce({
        // Default video limit setting
        ok: true,
        json: () => Promise.resolve({ limit: 10 })
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
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy' })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ limit: 10 })
        })
        .mockResolvedValueOnce({
          // Channel creation success
          ok: true,
          json: () => Promise.resolve({
            id: 1,
            url: 'https://www.youtube.com/@MrsRachel',
            name: 'Mrs. Rachel - Toddler Learning Videos',
            limit: 10,
            enabled: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          })
        })

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

      // Verify API call was made correctly
      expect(fetch).toHaveBeenCalledWith('/api/v1/channels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: 'https://www.youtube.com/@MrsRachel',
          enabled: true,
          quality_preset: 'best'
          // No limit field - should use default
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
      
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy' })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ limit: 10 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            id: 1,
            name: 'Test Channel',
            url: 'https://www.youtube.com/@TestChannel',
            limit: 10,
            enabled: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          })
        })

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
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy' })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ limit: 10 })
        })
        .mockResolvedValueOnce({
          // First channel addition
          ok: true,
          json: () => Promise.resolve({
            id: 1,
            name: 'First Channel',
            url: 'https://www.youtube.com/@FirstChannel',
            limit: 10,
            enabled: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          })
        })
        .mockResolvedValueOnce({
          // Second channel addition
          ok: true,
          json: () => Promise.resolve({
            id: 2,
            name: 'Second Channel',
            url: 'https://www.youtube.com/@SecondChannel',
            limit: 10,
            enabled: true,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z'
          })
        })

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

      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy' })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ limit: 10 })
        })
        .mockReturnValueOnce(slowPromise.then(() => ({
          ok: true,
          json: () => Promise.resolve({
            id: 1,
            name: 'Test Channel',
            url: 'https://www.youtube.com/@TestChannel',
            limit: 10,
            enabled: true,
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
      
      ;(fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy' })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ channels: [], total: 0 })
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({ limit: 10 })
        })
        .mockResolvedValueOnce({
          // API error response
          ok: false,
          json: () => Promise.resolve({ detail: 'Channel not found' })
        })

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