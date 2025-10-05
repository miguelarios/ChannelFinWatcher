import type { NextApiRequest, NextApiResponse } from 'next'

/**
 * Next.js API route proxy for cron expression validation (Story 007 - FE-001).
 *
 * This proxy route enables real-time validation of cron expressions in the
 * Settings UI. It validates the expression and returns next run times without
 * saving to the database.
 *
 * Architecture Pattern: Frontend -> Next.js API Route -> FastAPI Backend
 * - Frontend makes requests to /api/v1/scheduler/validate?expression=0%20*%2F6%20*%20*%20*
 * - This route proxies to backend:8000/api/v1/scheduler/validate
 * - Returns validation result with next run times
 * - Used for debounced real-time validation in UI
 *
 * Why This Route is Needed:
 * - Avoids CORS issues between frontend and backend containers
 * - Enables real-time validation feedback without saving
 * - Provides consistent error handling for invalid expressions
 * - Abstracts backend URL details from frontend components
 *
 * Supports:
 * - GET: Validate cron expression without saving
 * - Query param: expression (URL-encoded cron expression)
 * - Response: ValidateCronResponse with valid flag and next_5_runs
 * - Used for debounced input validation (500ms delay)
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

  // Extract expression from query params
  const { expression } = req.query

  if (!expression || typeof expression !== 'string') {
    return res.status(400).json({
      detail: 'Missing or invalid expression parameter',
      error: 'expression query parameter is required'
    })
  }

  try {
    // URL encode the expression for safe transmission
    const encodedExpression = encodeURIComponent(expression)
    const response = await fetch(
      `${backendUrl}/api/v1/scheduler/validate?expression=${encodedExpression}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

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
    console.error('Scheduler validate API proxy error:', error)
    res.status(500).json({
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend scheduler service',
      suggestion: 'Please ensure the backend service is running and accessible'
    })
  }
}
