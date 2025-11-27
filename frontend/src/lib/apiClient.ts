/**
 * Centralized API Client for Backend Communication
 *
 * This module provides a consistent, timeout-aware fetch wrapper for all
 * frontend-to-backend API calls. It solves the UND_ERR_HEADERS_TIMEOUT
 * error by configuring appropriate timeouts for different operation types.
 *
 * Why Different Timeouts?
 * - Video downloads can take 10+ minutes for large files
 * - Metadata operations may take 1-2 minutes for API calls
 * - Standard queries should fail fast (30 seconds)
 *
 * Usage:
 *   import { fetchBackend, OperationType } from '@/lib/apiClient'
 *
 *   // For quick operations (default 30s timeout)
 *   const { status, data } = await fetchBackend('/api/v1/channels')
 *
 *   // For long-running operations
 *   const { status, data } = await fetchBackend('/api/v1/channels/123/download', {
 *     method: 'POST',
 *     operationType: 'download'  // 10-minute timeout
 *   })
 */

/**
 * Operation types with their associated timeout values.
 * Timeouts are calibrated based on expected operation duration.
 */
export type OperationType = 'download' | 'metadata' | 'backfill' | 'standard'

/**
 * Timeout configuration in milliseconds.
 * These values can be overridden via environment variables.
 */
const TIMEOUT_DEFAULTS: Record<OperationType, number> = {
  download: 600000,   // 10 minutes - video downloads can be very slow
  metadata: 120000,   // 2 minutes - YouTube API calls, metadata fetching
  backfill: 300000,   // 5 minutes - NFO backfill operations
  standard: 30000,    // 30 seconds - quick queries, status checks
}

/**
 * Get timeout value for an operation type, with environment variable override support.
 */
function getTimeout(operationType: OperationType): number {
  const envKey = `API_TIMEOUT_${operationType.toUpperCase()}_MS`
  const envValue = process.env[envKey]
  if (envValue) {
    const parsed = parseInt(envValue, 10)
    if (!isNaN(parsed) && parsed > 0) {
      return parsed
    }
  }
  return TIMEOUT_DEFAULTS[operationType]
}

export interface FetchOptions {
  method?: string
  body?: unknown
  timeout?: number
  operationType?: OperationType
  headers?: Record<string, string>
}

export interface FetchResult<T = unknown> {
  status: number
  ok: boolean
  data: T
  timedOut?: boolean
}

/**
 * Custom error class for API timeout errors.
 * Allows callers to distinguish timeouts from other errors.
 */
export class ApiTimeoutError extends Error {
  constructor(
    public readonly endpoint: string,
    public readonly timeoutMs: number
  ) {
    super(`Request to ${endpoint} timed out after ${timeoutMs}ms`)
    this.name = 'ApiTimeoutError'
  }
}

/**
 * Fetch data from the backend with proper timeout handling.
 *
 * @param endpoint - The API endpoint path (e.g., '/api/v1/channels')
 * @param options - Fetch options including method, body, and timeout configuration
 * @returns Promise resolving to status, ok flag, and parsed data
 * @throws ApiTimeoutError if the request times out
 *
 * @example
 * // GET request with default timeout
 * const { status, data } = await fetchBackend('/api/v1/channels')
 *
 * @example
 * // POST request with download timeout
 * const { status, data } = await fetchBackend('/api/v1/channels/123/download', {
 *   method: 'POST',
 *   operationType: 'download'
 * })
 */
export async function fetchBackend<T = unknown>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<FetchResult<T>> {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000'
  const controller = new AbortController()

  // Determine timeout: explicit > operation type > default
  const timeoutMs =
    options.timeout ??
    getTimeout(options.operationType ?? 'standard')

  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const fetchOptions: RequestInit = {
      method: options.method ?? 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: controller.signal,
    }

    // Only include body for non-GET requests
    if (options.body !== undefined && options.method !== 'GET') {
      fetchOptions.body = JSON.stringify(options.body)
    }

    const response = await fetch(`${backendUrl}${endpoint}`, fetchOptions)

    // Parse response based on content type
    const contentType = response.headers.get('content-type')
    let data: T

    if (contentType?.includes('application/json')) {
      data = await response.json()
    } else {
      // Handle non-JSON responses (errors, HTML, etc.)
      const text = await response.text()
      data = {
        detail: 'Unexpected response format from backend',
        error: text || 'No response body',
        status: response.status,
      } as T
    }

    return {
      status: response.status,
      ok: response.ok,
      data,
    }
  } catch (error) {
    // Check if this was an abort (timeout)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiTimeoutError(endpoint, timeoutMs)
    }
    // Re-throw other errors
    throw error
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Handle API errors consistently, formatting them for the frontend.
 *
 * @param error - The caught error
 * @param context - A description of what operation was being attempted
 * @returns An object suitable for JSON response
 */
export function formatApiError(
  error: unknown,
  context: string
): { detail: string; error: string; suggestion?: string; timedOut?: boolean } {
  if (error instanceof ApiTimeoutError) {
    return {
      detail: `${context} request timed out`,
      error: `Backend took too long to respond (${error.timeoutMs / 1000}s timeout)`,
      suggestion: 'The operation may still be running. Try again in a moment.',
      timedOut: true,
    }
  }

  console.error(`${context} API proxy error:`, error)

  return {
    detail: 'Backend service unavailable',
    error: 'Failed to connect to backend',
    suggestion: 'Please ensure the backend service is running and accessible',
  }
}
