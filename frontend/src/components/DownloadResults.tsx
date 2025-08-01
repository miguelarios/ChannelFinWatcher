import React from 'react'
import { CheckCircleIcon, ClockIcon } from 'lucide-react'

interface Video {
  id: string
  title: string
  thumbnail: string
  duration: string
  size: string
  status: string
}

interface DownloadResultsProps {
  isLoading: boolean
  videos: Video[]
}

export function DownloadResults({ isLoading, videos }: DownloadResultsProps) {
  if (isLoading) {
    return (
      <div className="text-center py-8">
        <h3 className="text-lg font-medium mb-2">Processing Channel</h3>
        <p className="text-gray-500 mb-4">
          Please wait while we extract channel information...
        </p>
        <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4 max-w-md mx-auto">
          <div className="bg-red-600 h-2.5 rounded-full w-2/3 animate-pulse"></div>
        </div>
      </div>
    )
  }

  if (videos.length === 0) {
    return null
  }

  return (
    <div>
      <h3 className="text-lg font-medium mb-4">
        Channel Added Successfully ({videos.length} recent videos found)
      </h3>
      <div className="space-y-3">
        {videos.map((video) => (
          <div
            key={video.id}
            className="flex items-center border border-gray-200 rounded-lg p-3 hover:bg-gray-50"
          >
            <div className="flex-shrink-0 w-32 h-18 mr-4 relative">
              <img
                src={video.thumbnail}
                alt={video.title}
                className="w-full h-full object-cover rounded-md"
              />
              <span className="absolute bottom-1 right-1 bg-black bg-opacity-70 text-white text-xs px-1 rounded">
                {video.duration}
              </span>
            </div>
            <div className="flex-grow min-w-0">
              <h4 className="text-sm font-medium text-gray-900 truncate">
                {video.title}
              </h4>
              <p className="text-xs text-gray-500 mt-1">Size: {video.size}</p>
              <div className="flex items-center mt-2">
                {video.status === 'completed' ? (
                  <span className="inline-flex items-center text-xs text-green-600">
                    <CheckCircleIcon className="h-3.5 w-3.5 mr-1" />
                    Ready for Download
                  </span>
                ) : (
                  <span className="inline-flex items-center text-xs text-yellow-600">
                    <ClockIcon className="h-3.5 w-3.5 mr-1" />
                    Pending
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}