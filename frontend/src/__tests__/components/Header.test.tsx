import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { Header } from '../../components/Header'

/**
 * Header Component Tests
 * 
 * These tests verify the Header component behavior including:
 * - Proper rendering of branding and navigation
 * - View switching functionality
 * - Active state styling
 * - Accessibility features
 */

describe('Header Component', () => {
  const mockOnViewChange = jest.fn()
  
  beforeEach(() => {
    // Clear mock function calls before each test
    jest.clearAllMocks()
  })

  it('renders the application branding correctly', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    // Verify branding elements are present
    expect(screen.getByText('ChannelFinWatcher')).toBeInTheDocument()
    expect(screen.getByRole('banner')).toBeInTheDocument() // header has role="banner"
  })

  it('renders both navigation buttons', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    // Verify both navigation options are available
    expect(screen.getByRole('button', { name: /dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /settings/i })).toBeInTheDocument()
  })

  it('shows dashboard as active when currentView is dashboard', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const dashboardButton = screen.getByRole('button', { name: /dashboard/i })
    const settingsButton = screen.getByRole('button', { name: /settings/i })
    
    // Active button should have red-700 background (active state)
    expect(dashboardButton).toHaveClass('bg-red-700')
    expect(settingsButton).not.toHaveClass('bg-red-700')
  })

  it('shows settings as active when currentView is settings', () => {
    render(
      <Header 
        currentView="settings" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const dashboardButton = screen.getByRole('button', { name: /dashboard/i })
    const settingsButton = screen.getByRole('button', { name: /settings/i })
    
    // Settings button should be active
    expect(settingsButton).toHaveClass('bg-red-700')
    expect(dashboardButton).not.toHaveClass('bg-red-700')
  })

  it('calls onViewChange with "dashboard" when dashboard button is clicked', () => {
    render(
      <Header 
        currentView="settings" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const dashboardButton = screen.getByRole('button', { name: /dashboard/i })
    fireEvent.click(dashboardButton)
    
    // Verify the callback was called with correct parameter
    expect(mockOnViewChange).toHaveBeenCalledWith('dashboard')
    expect(mockOnViewChange).toHaveBeenCalledTimes(1)
  })

  it('calls onViewChange with "settings" when settings button is clicked', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const settingsButton = screen.getByRole('button', { name: /settings/i })
    fireEvent.click(settingsButton)
    
    // Verify the callback was called with correct parameter
    expect(mockOnViewChange).toHaveBeenCalledWith('settings')
    expect(mockOnViewChange).toHaveBeenCalledTimes(1)
  })

  it('applies hover styles to inactive navigation buttons', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const settingsButton = screen.getByRole('button', { name: /settings/i })
    
    // Inactive button should have hover styles available
    expect(settingsButton).toHaveClass('hover:text-white', 'hover:bg-red-700')
  })

  it('includes settings icon in settings button', () => {
    render(
      <Header 
        currentView="dashboard" 
        onViewChange={mockOnViewChange} 
      />
    )
    
    const settingsButton = screen.getByRole('button', { name: /settings/i })
    
    // Settings button should contain both icon and text
    expect(settingsButton).toHaveTextContent('Settings')
    // The Lucide icon will be rendered as an SVG
    expect(settingsButton.querySelector('svg')).toBeInTheDocument()
  })
})