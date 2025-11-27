import type { NextApiRequest, NextApiResponse } from 'next'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

/**
 * Next.js API route proxy for scheduler status (Story 007 - FE-001).
 *
 * This proxy route enables the Settings component to display current scheduler
 * status and configuration. It forwards requests from the frontend to the FastAPI
 * backend while handling container networking and error formatting.
 *
 * Architecture Pattern: Frontend -> Next.js API Route -> FastAPI Backend
 * - Frontend makes requests to /api/v1/scheduler/status
 * - This route proxies to backend:8000/api/v1/scheduler/status
 * - Handles container DNS resolution (backend:8000)
 * - Formats errors consistently for frontend consumption
 *
 * Why This Route is Needed:
 * - Avoids CORS issues between frontend and backend containers
 * - Provides consistent error handling and response formatting
 * - Enables easy switching between development and production backends
 * - Abstracts backend URL details from frontend components
 *
 * Supports:
 * - GET: Retrieve current scheduler status and configuration
 * - Returns: SchedulerStatusResponse with enabled state, cron schedule, next/last runs
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

  try {
    const { status, data } = await fetchBackend('/api/v1/scheduler/status', {
      method: 'GET',
      operationType: 'standard', // 30-second timeout for status checks
    })

    res.status(status).json(data)
  } catch (error) {
    const errorResponse = formatApiError(error, 'Scheduler status')
    res.status(errorResponse.timedOut ? 504 : 500).json(errorResponse)
  }
}
