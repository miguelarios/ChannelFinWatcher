import type { NextApiRequest, NextApiResponse } from 'next'

/**
 * Next.js API route proxy for default video limit settings.
 * 
 * This route forwards requests to the FastAPI backend's settings endpoints,
 * enabling the Settings component to retrieve and update the default video limit.
 * 
 * Supports:
 * - GET: Retrieve current default video limit setting
 * - PUT: Update default video limit setting with validation
 */
export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'
  
  // Only allow GET and PUT methods
  if (req.method !== 'GET' && req.method !== 'PUT') {
    return res.status(405).json({ 
      detail: 'Method not allowed',
      error: `${req.method} method not supported for this endpoint`
    })
  }
  
  try {
    const response = await fetch(`${backendUrl}/api/v1/settings/default-video-limit`, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method === 'PUT' ? JSON.stringify(req.body) : undefined,
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
    console.error('Settings API proxy error:', error)
    res.status(500).json({ 
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend settings service',
      suggestion: 'Please ensure the backend service is running and accessible'
    })
  }
}