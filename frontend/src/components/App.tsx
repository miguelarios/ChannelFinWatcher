import React, { useState } from 'react'
import { Header } from './Header'
import { YouTubeDownloader } from './YouTubeDownloader'
import { Settings } from './Settings'

type ViewType = 'dashboard' | 'settings'

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
        {currentView === 'dashboard' ? (
          <YouTubeDownloader onNavigateToSettings={() => handleViewChange('settings')} />
        ) : (
          <Settings />
        )}
      </main>
    </div>
  )
}