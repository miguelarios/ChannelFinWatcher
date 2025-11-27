import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for channel list and creation.
 *
 * Uses 'standard' timeout (30s) for GET requests (listing channels).
 * Uses 'metadata' timeout (2min) for POST requests (creating channels,
 * which may involve fetching YouTube metadata).
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    // POST (creating channels) may need more time for metadata fetching
    const operationType = req.method === 'POST' ? 'metadata' : 'standard'

    const { status, data } = await fetchBackend('/api/v1/channels', {
      method: req.method,
      body: req.method !== 'GET' ? req.body : undefined,
      operationType,
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Channels')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
