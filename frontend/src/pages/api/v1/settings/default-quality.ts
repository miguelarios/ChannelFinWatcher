import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for the default video quality preset setting (US-015).
 *
 * GET returns the current default; PUT updates it. Applies to new channels
 * only — existing channels keep their per-channel quality_preset.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET' && req.method !== 'PUT') {
    res.setHeader('Allow', ['GET', 'PUT'])
    return res.status(405).json({ error: `Method ${req.method} not allowed` })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/settings/default-quality', {
      method: req.method,
      body: req.method === 'PUT' ? req.body : undefined,
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Default quality setting')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
