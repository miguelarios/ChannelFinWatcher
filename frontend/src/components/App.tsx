import React, { useState } from 'react'
import { Header } from './Header'
import { ChannelStatusDashboard } from './ChannelStatusDashboard'
import { YouTubeDownloader } from './YouTubeDownloader'
import { DownloadHistory } from './DownloadHistory'
import { Settings } from './Settings'

type ViewType = 'dashboard' | 'channels' | 'history' | 'settings'

export function App() {
  const [currentView, setCurrentView] = useState<ViewType>('dashboard')

  const handleViewChange = (view: ViewType) => {
    setCurrentView(view)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header
        currentView={currentView}
        onViewChange={handleViewChange}
      />
      <main className="container mx-auto px-4 py-8">
        {currentView === 'dashboard' && (
          <ChannelStatusDashboard
            onNavigateToChannels={() => handleViewChange('channels')}
            onNavigateToSettings={() => handleViewChange('settings')}
          />
        )}
        {currentView === 'channels' && (
          <YouTubeDownloader onNavigateToSettings={() => handleViewChange('settings')} />
        )}
        {currentView === 'history' && <DownloadHistory />}
        {currentView === 'settings' && <Settings />}
      </main>
    </div>
  )
}
