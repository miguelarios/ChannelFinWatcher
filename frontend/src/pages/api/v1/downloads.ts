import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for the global download history list (US-011).
 *
 * Forwards filter/pagination query params (channel_id, status, limit, offset)
 * to the backend. Uses 'standard' timeout (30s) since this is a read-only query.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET'])
    return res.status(405).json({ error: `Method ${req.method} not allowed` })
  }

  try {
    const params = new URLSearchParams()
    const allowedParams = ['channel_id', 'status', 'limit', 'offset'] as const
    for (const key of allowedParams) {
      const value = req.query[key]
      if (typeof value === 'string' && value !== '') {
        params.set(key, value)
      }
    }

    const queryString = params.toString()
    const path = queryString ? `/api/v1/downloads?${queryString}` : '/api/v1/downloads'

    const { status, data } = await fetchBackend(path, {
      method: 'GET',
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Download history')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
