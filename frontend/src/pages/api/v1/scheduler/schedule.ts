import type { NextApiRequest, NextApiResponse } from 'next'

/**
 * Next.js API route proxy for scheduler schedule management (Story 007 - FE-001).
 *
 * This proxy route enables the Settings component to update the cron schedule
 * for automatic downloads. It validates the cron expression and returns the
 * next 5 scheduled run times for user verification.
 *
 * Architecture Pattern: Frontend -> Next.js API Route -> FastAPI Backend
 * - Frontend makes requests to /api/v1/scheduler/schedule
 * - This route proxies to backend:8000/api/v1/scheduler/schedule
 * - Handles validation errors (400 responses)
 * - Returns next run times for UI display
 *
 * Why This Route is Needed:
 * - Avoids CORS issues between frontend and backend containers
 * - Provides consistent error handling for invalid cron expressions
 * - Enables easy switching between development and production backends
 * - Abstracts backend URL details from frontend components
 *
 * Supports:
 * - POST: Update cron schedule with validation
 * - Request: {cron_expression: "0 0 * * *"}
 * - Response: UpdateScheduleResponse with next_5_runs array
 * - Error handling for invalid cron expressions (400 status)
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'

  // Only allow POST method
  if (req.method !== 'POST') {
    return res.status(405).json({
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }

  try {
    const response = await fetch(`${backendUrl}/api/v1/scheduler/schedule`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req.body),
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
      // Pass through error status (especially 400 for validation errors)
      res.status(response.status).json(data)
    }
  } catch (error) {
    console.error('Scheduler schedule API proxy error:', error)
    res.status(500).json({
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend scheduler service',
      suggestion: 'Please ensure the backend service is running and accessible'
    })
  }
}
