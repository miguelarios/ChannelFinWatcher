import type { NextApiRequest, NextApiResponse } from 'next'

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'
    const response = await fetch(`${backendUrl}/health`)
    const data = await response.json()
    res.status(200).json(data)
  } catch (error) {
    res.status(500).json({ status: 'error', message: 'Backend unreachable' })
  }
}