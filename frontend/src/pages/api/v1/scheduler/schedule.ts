import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * Next.js API route proxy for scheduler schedule management (Story 007 - FE-001).
 *
 * This proxy route enables the Settings component to update the cron schedule
 * for automatic downloads. It validates the cron expression and returns the
 * next 5 scheduled run times for user verification.
 *
 * Supports:
 * - POST: Update cron schedule with validation
 * - Request: {cron_expression: "0 0 * * *"}
 * - Response: UpdateScheduleResponse with next_5_runs array
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow POST method
  if (req.method !== 'POST') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  try {
    const { status, data } = await fetchBackend('/api/v1/scheduler/schedule', {
      method: 'POST',
      body: req.body,
      operationType: 'standard',
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Scheduler schedule')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
