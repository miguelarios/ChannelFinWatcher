import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for reindexing channel videos.
 *
 * Uses 'metadata' timeout (2 minutes) since this involves
 * scanning video files on disk.
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
      `/api/v1/channels/${id}/reindex`,
      {
        method: 'POST',
        operationType: 'metadata', // 2-minute timeout for disk scanning
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Reindex')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
