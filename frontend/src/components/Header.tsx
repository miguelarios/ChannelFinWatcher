import React from 'react'
import { YoutubeIcon, Settings as SettingsIcon } from 'lucide-react'

interface HeaderProps {
  currentView: 'dashboard' | 'settings'
  onViewChange: (view: 'dashboard' | 'settings') => void
}

export function Header({ currentView, onViewChange }: HeaderProps) {
  return (
    <header className="bg-red-600 text-white shadow-md">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <div className="flex items-center">
          <YoutubeIcon className="h-8 w-8 mr-3" />
          <h1 className="text-2xl font-bold">ChannelFinWatcher</h1>
        </div>
        
        {/* Navigation */}
        <nav className="flex items-center space-x-4">
          <button
            onClick={() => onViewChange('dashboard')}
            className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              currentView === 'dashboard'
                ? 'bg-red-700 text-white'
                : 'text-red-100 hover:text-white hover:bg-red-700'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => onViewChange('settings')}
            className={`inline-flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              currentView === 'settings'
                ? 'bg-red-700 text-white'
                : 'text-red-100 hover:text-white hover:bg-red-700'
            }`}
          >
            <SettingsIcon className="h-4 w-4 mr-2" />
            Settings
          </button>
        </nav>
      </div>
    </header>
  )
}