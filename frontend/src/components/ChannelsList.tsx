import React from 'react'
import { YoutubeIcon, TrashIcon, CheckCircleIcon } from 'lucide-react'

interface Channel {
  id: number
  url: string
  name: string
  limit: number
  enabled: boolean
  created_at: string
  updated_at: string
}

interface ChannelsListProps {
  channels: Channel[]
  selectedChannelId: number | null
  onSelectChannel: (channelId: number) => void
  onRemoveChannel: (channelId: number) => void
}

export function ChannelsList({
  channels,
  selectedChannelId,
  onSelectChannel,
  onRemoveChannel,
}: ChannelsListProps) {
  if (!channels || channels.length === 0) {
    return null
  }

  return (
    <div>
      <h3 className="text-lg font-medium mb-4">Your Channels</h3>
      <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
        {channels.map((channel) => (
          <div
            key={channel.id}
            className={`flex items-center justify-between border rounded-lg p-3 hover:bg-gray-50 cursor-pointer ${
              selectedChannelId === channel.id ? 'border-red-500 bg-red-50' : 'border-gray-200'
            }`}
            onClick={() => onSelectChannel(channel.id)}
          >
            <div className="flex items-center flex-grow min-w-0">
              <YoutubeIcon className="h-5 w-5 text-red-600 mr-3 flex-shrink-0" />
              <div className="min-w-0">
                <h4 className="text-sm font-medium text-gray-900 truncate">
                  {channel.name}
                </h4>
                <p className="text-xs text-gray-500 truncate mt-0.5">
                  {channel.url}
                </p>
              </div>
            </div>
            <div className="flex items-center ml-4">
              <span className="text-xs text-gray-600 mr-3">
                Limit: {channel.limit}
              </span>
              {selectedChannelId === channel.id && (
                <CheckCircleIcon className="h-4 w-4 text-green-600 mr-2" />
              )}
              <button
                className="text-gray-400 hover:text-red-600 p-1"
                onClick={(e) => {
                  e.stopPropagation()
                  onRemoveChannel(channel.id)
                }}
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}