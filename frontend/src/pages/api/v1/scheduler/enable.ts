import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * Next.js API route proxy for scheduler enable/disable toggle (Story 007 - FE-001).
 *
 * This proxy route enables the Settings component to toggle the scheduler
 * on/off without changing the cron schedule configuration. When disabled,
 * scheduled downloads will not run, but the schedule is preserved.
 *
 * Supports:
 * - PUT: Enable or disable scheduler
 * - Request: {enabled: boolean}
 * - Response: {success: true, enabled: boolean, message: string}
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow PUT method
  if (req.method !== 'PUT') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/scheduler/enable', {
      method: 'PUT',
      body: req.body,
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Scheduler enable')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
