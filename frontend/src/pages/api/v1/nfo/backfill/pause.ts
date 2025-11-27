import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for pausing NFO backfill operations.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/nfo/backfill/pause', {
      method: 'POST',
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'NFO backfill pause')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
