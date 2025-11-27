import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for refreshing channel metadata from YouTube.
 *
 * Uses 'metadata' timeout (2 minutes) since this involves
 * YouTube API calls and potentially downloading assets.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id } = req.query

  // Only allow POST method for refresh
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST'])
    res.status(405).json({ detail: 'Method Not Allowed' })
    return
  }

  try {
    const { status, data } = await fetchBackend(
      `/api/v1/channels/${id}/refresh-metadata`,
      {
        method: 'POST',
        operationType: 'metadata', // 2-minute timeout for YouTube API calls
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Refresh metadata')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
