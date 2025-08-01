import React from 'react'
import { YoutubeIcon } from 'lucide-react'

export function Header() {
  return (
    <header className="bg-red-600 text-white shadow-md">
      <div className="container mx-auto px-4 py-4 flex items-center">
        <YoutubeIcon className="h-8 w-8 mr-3" />
        <h1 className="text-2xl font-bold">ChannelFinWatcher</h1>
      </div>
    </header>
  )
}