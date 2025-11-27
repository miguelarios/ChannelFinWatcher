import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for triggering channel video downloads.
 *
 * Uses 'download' operation type for a 10-minute timeout, since video
 * downloads can take significant time depending on file sizes and
 * network conditions.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id } = req.query

  // Only allow POST method for download
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST'])
    res.status(405).json({ detail: 'Method Not Allowed' })
    return
  }

  try {
    const { status, data } = await fetchBackend(
      `/api/v1/channels/${id}/download`,
      {
        method: 'POST',
        operationType: 'download', // 10-minute timeout for video downloads
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Download')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
