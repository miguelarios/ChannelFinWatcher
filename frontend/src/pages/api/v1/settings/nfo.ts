import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for NFO settings.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const { status, data } = await fetchBackend('/api/v1/settings/nfo', {
      method: req.method,
      body: req.method !== 'GET' ? req.body : undefined,
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'NFO settings')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
