import type { NextApiRequest, NextApiResponse } from 'next'

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
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'

  // Only allow GET method
  if (req.method !== 'GET') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  try {
    const response = await fetch(`${backendUrl}/api/v1/scheduler/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Handle different response scenarios
    let data
    const contentType = response.headers.get('content-type')

    if (contentType && contentType.includes('application/json')) {
      data = await response.json()
    } else {
      // Handle non-JSON responses (errors, etc.)
      const text = await response.text()
      data = {
        detail: 'Unexpected response format from backend',
        error: text || 'No response body',
        status: response.status
      }
    }

    if (response.ok) {
      res.status(200).json(data)
    } else {
      res.status(response.status).json(data)
    }
  } catch (error) {
    console.error('Scheduler status API proxy error:', error)
    res.status(500).json({
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend scheduler service',
      suggestion: 'Please ensure the backend service is running and accessible'
    })
  }
}
