import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/** Proxy for the YouTube cookies file health status. */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET'])
    return res.status(405).json({ error: `Method ${req.method} not allowed` })
  }
  try {
    const { status, data } = await fetchBackend('/api/v1/settings/cookies-status', {
      method: 'GET',
      operationType: 'standard',
    })
    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Cookies status')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
