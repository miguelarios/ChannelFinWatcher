import type { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'GET') {
    return res.status(405).json({ detail: 'Method not allowed' })
  }

  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'

  try {
    const response = await fetch(`${backendUrl}/api/v1/nfo/backfill/status`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
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
