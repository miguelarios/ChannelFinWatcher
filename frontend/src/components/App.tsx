import React from 'react'
import { Header } from './Header'
import { YouTubeDownloader } from './YouTubeDownloader'

export function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <YouTubeDownloader />
      </main>
    </div>
  )
}