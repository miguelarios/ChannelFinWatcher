import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend } from '@/lib/apiClient'

/**
 * Health check endpoint for backend connectivity.
 * Uses a short timeout (10 seconds) since health checks should be fast.
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const { data } = await fetchBackend('/health', {
      method: 'GET',
      timeout: 10000, // 10-second timeout for health checks
    })
    res.status(200).json(data)
  } catch {
    res.status(500).json({ status: 'error', message: 'Backend unreachable' })
  }
}
