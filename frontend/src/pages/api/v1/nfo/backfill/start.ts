import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for starting NFO backfill operations.
 *
 * Uses 'backfill' timeout (5 minutes) since this can be a long-running
 * operation that processes many files.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/nfo/backfill/start', {
      method: 'POST',
      operationType: 'backfill', // 5-minute timeout for backfill operations
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'NFO backfill start')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
