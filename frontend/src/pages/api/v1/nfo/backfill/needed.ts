import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for checking NFO backfill needs.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ detail: 'Method not allowed' })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/nfo/backfill/needed', {
      method: 'GET',
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'NFO backfill needed')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
