import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * API route proxy for individual channel operations.
 *
 * Uses 'standard' timeout for GET requests.
 * Uses 'metadata' timeout for PUT/DELETE (may involve file operations).
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id, delete_media } = req.query

  try {
    // Build endpoint with query params for DELETE
    let endpoint = `/api/v1/channels/${id}`
    if (req.method === 'DELETE' && delete_media !== undefined) {
      endpoint += `?delete_media=${delete_media === 'true'}`
    }

    // DELETE may involve file operations, use metadata timeout
    const operationType = req.method === 'DELETE' ? 'metadata' : 'standard'

    const { status, data } = await fetchBackend(endpoint, {
      method: req.method,
      body: req.method !== 'GET' && req.method !== 'DELETE' ? req.body : undefined,
      operationType,
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Channel')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
