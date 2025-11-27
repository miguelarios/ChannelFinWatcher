import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * Next.js API route proxy for default video limit settings (User Story 3).
 *
 * Supports:
 * - GET: Retrieve current default video limit setting
 * - PUT: Update default video limit setting with validation
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow GET and PUT methods
  if (req.method !== 'GET' && req.method !== 'PUT') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  try {
    const { status, data } = await fetchBackend(
      '/api/v1/settings/default-video-limit',
      {
        method: req.method,
        body: req.method === 'PUT' ? req.body : undefined,
        operationType: 'standard',
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Settings')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
