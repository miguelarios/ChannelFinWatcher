import type { NextApiRequest, NextApiResponse } from 'next'
import handler from '@/pages/api/v1/downloads/[id]/retry'
import { fetchBackend, formatApiError } from '@/lib/apiClient'

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

describe('/api/v1/downloads/[id]/retry proxy', () => {
  beforeEach(() => jest.clearAllMocks())

  it('forwards POST to the backend with the download timeout', async () => {
    const payload = { success: true }
    ;(fetchBackend as jest.Mock).mockResolvedValue({ status: 200, data: payload })
    const res = mockRes()

    await handler({ method: 'POST', query: { id: '1293' } } as unknown as NextApiRequest, res)

    expect(fetchBackend).toHaveBeenCalledWith('/api/v1/downloads/1293/retry', {
      method: 'POST',
      operationType: 'download',
    })
    expect(res.status).toHaveBeenCalledWith(200)
    expect(res.json).toHaveBeenCalledWith(payload)
  })

  it('relays backend 4xx responses unchanged', async () => {
    const payload = { detail: 'Download is not in failed state' }
    ;(fetchBackend as jest.Mock).mockResolvedValue({ status: 400, data: payload })
    const res = mockRes()

    await handler({ method: 'POST', query: { id: '7' } } as unknown as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(400)
    expect(res.json).toHaveBeenCalledWith(payload)
  })

  it('maps a backend timeout to 504', async () => {
    // A synchronous retry can run up to the 10-minute download timeout,
    // so this is the proxy most likely to actually time out.
    ;(fetchBackend as jest.Mock).mockRejectedValue(new Error('timeout'))
    ;(formatApiError as jest.Mock).mockReturnValueOnce({ error: 'Retry timed out', timedOut: true })
    const res = mockRes()

    await handler({ method: 'POST', query: { id: '7' } } as unknown as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(504)
  })

  it('returns 500 when the backend is unreachable', async () => {
    ;(fetchBackend as jest.Mock).mockRejectedValue(new Error('ECONNREFUSED'))
    const res = mockRes()

    await handler({ method: 'POST', query: { id: '7' } } as unknown as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(500)
  })

  it('rejects non-POST methods', async () => {
    const res = mockRes()

    await handler({ method: 'GET', query: { id: '7' } } as unknown as NextApiRequest, res)

    expect(res.status).toHaveBeenCalledWith(405)
    expect(fetchBackend).not.toHaveBeenCalled()
  })
})
