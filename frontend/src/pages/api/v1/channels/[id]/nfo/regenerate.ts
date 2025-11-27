import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for regenerating NFO files for a channel.
 *
 * Uses 'standard' timeout since NFO regeneration for a single
 * channel is typically fast.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ detail: 'Method not allowed' })
  }

  const { id } = req.query

  try {
    const { status, data } = await fetchBackend(
      `/api/v1/channels/${id}/nfo/regenerate`,
      {
        method: 'POST',
        operationType: 'standard',
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'NFO regenerate')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
