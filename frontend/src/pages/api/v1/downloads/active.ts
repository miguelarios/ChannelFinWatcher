import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for in-flight download progress (US-010).
 *
 * ActiveDownloads polls this every 2 seconds. Without this route the request
 * falls through to a Next.js 404 and the progress bar never renders, even
 * though the backend serves /api/v1/downloads/active.
 *
 * The backend also offers an SSE stream (/downloads/progress/stream), but the
 * pages-router proxy buffers streaming responses, so the UI polls instead.
 * Uses 'standard' timeout (30s) since this is a read-only snapshot.
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
    const { status, data } = await fetchBackend('/api/v1/downloads/active', {
      method: 'GET',
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Active downloads')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
