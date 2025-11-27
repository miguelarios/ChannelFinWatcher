import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * Next.js API route proxy for cron expression validation (Story 007 - FE-001).
 *
 * This proxy route enables real-time validation of cron expressions in the
 * Settings UI. It validates the expression and returns next run times without
 * saving to the database.
 *
 * Supports:
 * - GET: Validate cron expression without saving
 * - Query param: expression (URL-encoded cron expression)
 * - Response: ValidateCronResponse with valid flag and next_5_runs
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow GET method
  if (req.method !== 'GET') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  // Extract expression from query params
  const { expression } = req.query

  if (!expression || typeof expression !== 'string') {
    return res.status(400).json({
      detail: 'Missing or invalid expression parameter',
      error: 'expression query parameter is required'
    })
  }

  try {
    const encodedExpression = encodeURIComponent(expression)
    const { status, data } = await fetchBackend(
      `/api/v1/scheduler/validate?expression=${encodedExpression}`,
      {
        method: 'GET',
        operationType: 'standard',
      }
    )

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Scheduler validate')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
