import type { NextApiRequest, NextApiResponse } from 'next'
import handler from '@/pages/api/v1/downloads/active'
import { fetchBackend } from '@/lib/apiClient'

jest.mock('@/lib/apiClient', () => ({
  fetchBackend: jest.fn(),
  formatApiError: jest.fn(() => ({ error: 'boom', timedOut: false })),
}))

function mockRes() {
  const res: Partial<NextApiResponse> = {}
  res.status = jest.fn(() => res as NextApiResponse)
  res.json = jest.fn(() => res as NextApiResponse)
  res.setHeader = jest.fn(() => res as NextApiResponse)
  return res as NextApiResponse
}

describe('/api/v1/downloads/active proxy', () => {
  beforeEach(() => jest.clearAllMocks())

  it('forwards GET to the backend and relays the response', async () => {
    const payload = { active: [], count: 0 }
    ;(fetchBackend as jest.Mock).mockResolvedValue({ status: 200, data: payload })
    const res = mockRes()

    await handler({ method: 'GET' } as NextApiRequest, res)

    expect(fetchBackend).toHaveBeenCalledWith('/api/v1/downloads/active', {
      method: 'GET',
      operationType: 'standard',
    })
    expect(res.status).toHaveBeenCalledWith(200)
    expect(res.json).toHaveBeenCalledWith(payload)
  })

  it('rejects non-GET methods', async () => {
    const res = mockRes()

    await handler({ method: 'POST' } as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(405)
    expect(fetchBackend).not.toHaveBeenCalled()
  })

  it('returns 500 when the backend is unreachable', async () => {
    ;(fetchBackend as jest.Mock).mockRejectedValue(new Error('ECONNREFUSED'))
    const res = mockRes()

    await handler({ method: 'GET' } as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(500)
  })
})
