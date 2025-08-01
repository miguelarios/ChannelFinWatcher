import type { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'
  
  try {
    const response = await fetch(`${backendUrl}/api/v1/channels`, {
      method: req.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
    })

    const data = await response.json()
    
    if (response.ok) {
      res.status(200).json(data)
    } else {
      res.status(response.status).json(data)
    }
  } catch (error) {
    console.error('API proxy error:', error)
    res.status(500).json({ 
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend'
    })
  }
}