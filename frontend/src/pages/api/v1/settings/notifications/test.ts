import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/** Proxy for sending a test notification. */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST'])
    return res.status(405).json({ error: `Method ${req.method} not allowed` })
  }
  try {
    const { status, data } = await fetchBackend('/api/v1/settings/notifications/test', {
      method: 'POST',
      operationType: 'standard',
    })
    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Test notification')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
