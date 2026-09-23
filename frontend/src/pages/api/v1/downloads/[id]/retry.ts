import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for retrying a single failed download (per-video retry).
 *
 * DownloadHistory's Retry button POSTs here. Without this route the request
 * falls through to a Next.js 404, even though the backend serves
 * POST /api/v1/downloads/{id}/retry.
 *
 * Uses 'download' operation type for a 10-minute timeout: the backend runs
 * the download synchronously, including its within-run retry backoff.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id } = req.query

  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST'])
    return res.status(405).json({ detail: 'Method Not Allowed' })
  }

  try {
    const { status, data } = await fetchBackend(
      `/api/v1/downloads/${encodeURIComponent(String(id))}/retry`,
      {
        method: 'POST',
        operationType: 'download',
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Retry')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
