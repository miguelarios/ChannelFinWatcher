import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { ChannelsList } from '../../components/ChannelsList'

/**
 * ChannelsList Component Tests
 * 
 * Tests the core functionality of User Story 2: Configure Channel Video Limit
 * including inline editing, validation, confirmation dialogs, and API integration.
 */

// Mock fetch globally for API testing
global.fetch = jest.fn()

describe('ChannelsList Component', () => {
  const mockOnSelectChannel = jest.fn()
  const mockOnRemoveChannel = jest.fn() 
  const mockOnUpdateChannel = jest.fn()
  
  const sampleChannels = [
    {
      id: 1,
      url: 'https://www.youtube.com/@MrsRachel',
      name: 'Mrs. Rachel - Toddler Learning Videos',
      limit: 10,
      enabled: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      metadata_status: 'completed',
      metadata_path: '/media/channel1',
      directory_path: '/media/Mrs. Rachel [UC123]',
      last_metadata_update: '2024-01-01T00:00:00Z',
      cover_image_path: '/media/cover.jpg',
      backdrop_image_path: '/media/backdrop.jpg'
    },
    {
      id: 2,
      url: 'https://www.youtube.com/@TestChannel',
      name: 'Test Channel',
      limit: 25,
      enabled: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      metadata_status: 'pending',
      metadata_path: '/media/channel2',
      directory_path: '/media/Test Channel [UC456]',
      last_metadata_update: '2024-01-01T00:00:00Z',
      cover_image_path: '/media/cover2.jpg',
      backdrop_image_path: '/media/backdrop2.jpg'
    }
  ]

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks()
    ;(fetch as jest.Mock).mockClear()
  })

  afterEach(() => {
    // Clean up any pending timers only if fake timers are active
    try {
      if (jest.isMockFunction(setTimeout)) {
        jest.runOnlyPendingTimers()
        jest.useRealTimers()
      }
    } catch (e) {
      // Ignore errors if timers aren't active
    }
  })

  describe('Basic Rendering', () => {
    it('renders null when channels array is empty', () => {
      const { container } = render(
        <ChannelsList
          channels={[]}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )
      expect(container.firstChild).toBeNull()
    })

    it('renders all provided channels', () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // Both channels should be rendered
      expect(screen.getByText('Mrs. Rachel - Toddler Learning Videos')).toBeInTheDocument()
      expect(screen.getByText('Test Channel')).toBeInTheDocument()
      expect(screen.getByText('Limit: 10')).toBeInTheDocument()
      expect(screen.getByText('Limit: 25')).toBeInTheDocument()
    })

    it('highlights selected channel with special styling', () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={1}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // The channel name is nested inside inner layout divs; the selection
      // classes live on the clickable row container (cursor-pointer)
      const channelRow = screen.getByText('Mrs. Rachel - Toddler Learning Videos').closest('div.cursor-pointer')

      // Selected channel should have red border styling
      expect(channelRow).toHaveClass('border-red-500', 'bg-red-50')
    })
  })

  describe('Channel Selection', () => {
    it('calls onSelectChannel when channel is clicked', () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // Click on the first channel
      const channelElement = screen.getByText('Mrs. Rachel - Toddler Learning Videos')
      fireEvent.click(channelElement)

      expect(mockOnSelectChannel).toHaveBeenCalledWith(1)
    })

    it('shows delete modal when remove button is clicked', () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // Delete now lives in the kebab menu: open it, then click the item
      fireEvent.click(screen.getAllByTitle('More actions')[0])
      fireEvent.click(screen.getByRole('button', { name: /delete channel/i }))

      // Should show confirmation modal instead of immediately deleting
      expect(screen.getByText('Confirm Channel Deletion')).toBeInTheDocument()
      expect(screen.getByText('Also delete media files (permanent)')).toBeInTheDocument()
    })
  })

  describe('Inline Limit Editing', () => {
    it('enters edit mode when edit button is clicked', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Click edit button for first channel
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)

      // Should show number input in edit mode
      expect(screen.getByDisplayValue('10')).toBeInTheDocument()
      expect(screen.getByTitle('Save (Enter)')).toBeInTheDocument()
      expect(screen.getByTitle('Cancel (Escape)')).toBeInTheDocument()
    })

    it('enters edit mode when limit text is clicked', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Click on the limit text itself
      const limitText = screen.getByText('Limit: 10')
      await user.click(limitText)

      // Should enter edit mode
      expect(screen.getByDisplayValue('10')).toBeInTheDocument()
    })

    it('cancels edit mode when cancel button is clicked', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)

      // Cancel editing
      const cancelButton = screen.getByTitle('Cancel (Escape)')
      await user.click(cancelButton)

      // Should exit edit mode
      expect(screen.queryByDisplayValue('10')).not.toBeInTheDocument()
      expect(screen.getByText('Limit: 10')).toBeInTheDocument()
    })

    it('cancels edit mode when Escape key is pressed', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)

      // Press Escape
      const input = screen.getByDisplayValue('10')
      await user.type(input, '{Escape}')

      // Should exit edit mode
      await waitFor(() => {
        expect(screen.queryByDisplayValue('10')).not.toBeInTheDocument()
      })
    })
  })

  describe('Limit Update API Integration', () => {
    it('successfully updates limit via API', async () => {
      const user = userEvent.setup()
      
      // Mock successful API response
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, limit: 15 })
      })
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)

      // Change value and save
      const input = screen.getByDisplayValue('10')
      await user.clear(input)
      await user.type(input, '15')
      await user.type(input, '{Enter}')

      // Verify API call
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/v1/channels/1', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ limit: 15 })
        })
      })

      // Verify parent component callback
      expect(mockOnUpdateChannel).toHaveBeenCalledWith(1, { limit: 15 })
    })

    it('shows error message when API call fails', async () => {
      const user = userEvent.setup()
      
      // Mock failed API response
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Validation error' })
      })
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode and try to save
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)
      
      const saveButton = screen.getByTitle('Save (Enter)')
      await user.click(saveButton)

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText('Validation error')).toBeInTheDocument()
      })
    })

    it('validates limit range and shows error for invalid values', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode
      const editButton = screen.getAllByTitle('Edit limit')[0]
      await user.click(editButton)

      // Try invalid value (too high)
      const input = screen.getByDisplayValue('10')
      await user.clear(input)
      await user.type(input, '150')
      
      const saveButton = screen.getByTitle('Save (Enter)')
      await user.click(saveButton)

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText('Limit must be between 1 and 100')).toBeInTheDocument()
      })

      // API should not be called
      expect(fetch).not.toHaveBeenCalled()
    })
  })

  describe('Confirmation Dialog for Large Reductions', () => {
    it('shows confirmation dialog for significant limit reductions', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode for channel with limit 25
      const editButtons = screen.getAllByTitle('Edit limit')
      await user.click(editButtons[1]) // Second channel with limit 25

      // Reduce limit significantly (from 25 to 5 = 80% reduction)
      const input = screen.getByDisplayValue('25')
      await user.clear(input)
      await user.type(input, '5')
      await user.type(input, '{Enter}')

      // Should show confirmation dialog. The from/to numbers are wrapped in
      // <strong> tags, so match on the dialog's combined text content.
      await waitFor(() => {
        expect(screen.getByText('Confirm Limit Reduction')).toBeInTheDocument()
        const dialog = screen.getByText('Confirm Limit Reduction').closest('div')
        expect(dialog).toHaveTextContent(/reducing the video limit from 25 to 5/i)
      })
    })

    it('proceeds with update when user confirms significant reduction', async () => {
      const user = userEvent.setup()
      
      // Mock successful API response
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 2, limit: 5 })
      })
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Enter edit mode and trigger confirmation dialog
      const editButtons = screen.getAllByTitle('Edit limit')
      await user.click(editButtons[1])
      
      const input = screen.getByDisplayValue('25')
      await user.clear(input)
      await user.type(input, '5')
      await user.type(input, '{Enter}')

      // Confirm the reduction
      await waitFor(() => {
        expect(screen.getByText('Confirm')).toBeInTheDocument()
      })
      
      const confirmButton = screen.getByText('Confirm')
      await user.click(confirmButton)

      // Should make API call
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/v1/channels/2', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ limit: 5 })
        })
      })
    })

    it('cancels update when user rejects confirmation dialog', async () => {
      const user = userEvent.setup()
      
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Trigger confirmation dialog
      const editButtons = screen.getAllByTitle('Edit limit')
      await user.click(editButtons[1])
      
      const input = screen.getByDisplayValue('25')
      await user.clear(input)
      await user.type(input, '5')
      await user.type(input, '{Enter}')

      // Cancel the reduction
      await waitFor(() => {
        expect(screen.getByText('Cancel')).toBeInTheDocument()
      })
      
      const cancelButton = screen.getByText('Cancel')
      await user.click(cancelButton)

      // Dialog should close and no API call should be made
      await waitFor(() => {
        expect(screen.queryByText('Confirm Limit Reduction')).not.toBeInTheDocument()
      })
      expect(fetch).not.toHaveBeenCalled()
    })
  })

  // Row actions moved into a kebab menu ("More actions") — open it first,
  // then click the labeled menu item
  const clickKebabMenuItem = (itemName: RegExp, rowIndex = 0) => {
    fireEvent.click(screen.getAllByTitle('More actions')[rowIndex])
    fireEvent.click(screen.getByRole('button', { name: itemName }))
  }

  describe('Quality Preset (US-015)', () => {
    it('updates channel quality via the kebab menu select', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 1, quality_preset: '720p' }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
          onUpdateChannel={mockOnUpdateChannel}
        />
      )

      // Open the kebab menu and change the quality select
      fireEvent.click(screen.getAllByTitle('More actions')[0])
      const select = screen.getByLabelText(/video quality for/i)
      fireEvent.change(select, { target: { value: '720p' } })

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith('/api/v1/channels/1', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ quality_preset: '720p' }),
        })
      })

      await waitFor(() => {
        expect(mockOnUpdateChannel).toHaveBeenCalledWith(1, { quality_preset: '720p' })
      })
    })
  })

  describe('Delete Modal Functionality', () => {
    it('shows delete modal when delete button clicked', async () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/delete channel/i)

      expect(screen.getByText('Confirm Channel Deletion')).toBeInTheDocument()
      expect(screen.getByText('Also delete media files (permanent)')).toBeInTheDocument()
    })

    it('calls API with delete_media=false when modal confirmed without checkbox', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Channel deleted successfully' }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/delete channel/i)
      fireEvent.click(screen.getByText('Delete Channel'))

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/v1/channels/1?delete_media=false',
          expect.objectContaining({ method: 'DELETE' })
        )
      })
    })

    it('calls API with delete_media=true when checkbox checked', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ 
          message: 'Channel deleted successfully', 
          media_deleted: true, 
          files_deleted: 5 
        }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/delete channel/i)
      fireEvent.click(screen.getByLabelText('Also delete media files (permanent)'))
      fireEvent.click(screen.getByText('Delete Channel'))

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/v1/channels/1?delete_media=true',
          expect.objectContaining({ method: 'DELETE' })
        )
      })
    })

    it('cancels modal when Cancel button is clicked', async () => {
      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // Open modal via the kebab menu
      clickKebabMenuItem(/delete channel/i)
      expect(screen.getByText('Confirm Channel Deletion')).toBeInTheDocument()

      // Cancel
      fireEvent.click(screen.getByText('Cancel'))
      
      await waitFor(() => {
        expect(screen.queryByText('Confirm Channel Deletion')).not.toBeInTheDocument()
      })
    })
  })

  describe('Reindex Functionality', () => {
    it('calls reindex API when reindex button clicked', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ found: 2, missing: 1, added: 0 }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/reindex media/i)

      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/v1/channels/1/reindex',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          })
        )
      })
    })

    it('displays reindex results after successful operation', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ found: 2, missing: 1, added: 3 }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/reindex media/i)

      await waitFor(() => {
        expect(screen.getByText('Reindex complete - found 2, added 3, missing 1')).toBeInTheDocument()
      })
    })

    it('displays error message when reindex fails', async () => {
      ;(fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Reindex failed' }),
      })

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      clickKebabMenuItem(/reindex media/i)

      await waitFor(() => {
        expect(screen.getByText('Reindex failed')).toBeInTheDocument()
      })
    })

    it('shows loading state during reindex operation', async () => {
      // Mock a delayed response
      ;(fetch as jest.Mock).mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          ok: true,
          json: async () => ({ found: 1, missing: 0, added: 0 })
        }), 100))
      )

      render(
        <ChannelsList
          channels={sampleChannels}
          selectedChannelId={null}
          onSelectChannel={mockOnSelectChannel}
          onRemoveChannel={mockOnRemoveChannel}
        />
      )

      // Trigger reindex via the kebab menu (the menu closes on click)
      clickKebabMenuItem(/reindex media/i)

      // Re-open the menu: while the operation runs, the reindex item is disabled
      fireEvent.click(screen.getAllByTitle('More actions')[0])
      expect(screen.getByRole('button', { name: /reindex media/i })).toBeDisabled()

      // Wait for operation to complete
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reindex media/i })).not.toBeDisabled()
      }, { timeout: 300 })
    })
  })
})