import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for the channel status dashboard (US-009/US-012).
 *
 * Read-only aggregate, so the 'standard' 30s timeout applies.
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
    const { status, data } = await fetchBackend('/api/v1/dashboard', {
      method: 'GET',
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Dashboard')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
