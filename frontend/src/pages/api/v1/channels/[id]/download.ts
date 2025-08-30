import type { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  const { id } = req.query
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'
  
  // Only allow POST method for download
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST'])
    res.status(405).json({ detail: 'Method Not Allowed' })
    return
  }
  
  try {
    const response = await fetch(`${backendUrl}/api/v1/channels/${id}/download`, {
      method: 'POST',
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
    console.error('Download API proxy error:', error)
    res.status(500).json({ 
      detail: 'Backend service unavailable',
      error: 'Failed to connect to backend'
    })
  }
}