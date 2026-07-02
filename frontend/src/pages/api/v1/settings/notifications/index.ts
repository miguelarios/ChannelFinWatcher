import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/** Proxy for reading/updating the Apprise notification URL. */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET' && req.method !== 'PUT') {
    res.setHeader('Allow', ['GET', 'PUT'])
    return res.status(405).json({ error: `Method ${req.method} not allowed` })
  }
  try {
    const { status, data } = await fetchBackend('/api/v1/settings/notifications', {
      method: req.method,
      body: req.method === 'PUT' ? req.body : undefined,
      operationType: 'standard',
    })
    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Notification settings')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
