import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: unknown
  timeoutMs?: number
}

export class ApiError extends Error {
  status: number
  data: unknown
  isNetworkError: boolean

  constructor(message: string, options: { status: number; data?: unknown; isNetworkError?: boolean }) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.data = options.data
    this.isNetworkError = options.isNetworkError ?? false
  }
}

async function getAccessToken(): Promise<string | null> {
  const { data, error } = await supabase.auth.getSession()

  if (error) {
    throw new ApiError(error.message, {
      status: 0,
      data: error,
      isNetworkError: true,
    })
  }

  return data.session?.access_token ?? null
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''

  if (response.status === 204) {
    return null
  }

  if (contentType.includes('application/json')) {
    return response.json()
  }

  return response.text()
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers, timeoutMs = 30_000, ...init } = options
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const token = await getAccessToken()
    const requestHeaders = new Headers(headers)

    if (body !== undefined && !requestHeaders.has('Content-Type')) {
      requestHeaders.set('Content-Type', 'application/json')
    }

    if (token) {
      requestHeaders.set('Authorization', `Bearer ${token}`)
    }

    const response = await fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: requestHeaders,
      signal: controller.signal,
    })
    const data = await parseResponse(response)

    if (!response.ok) {
      throw new ApiError(`Request failed with status ${response.status}`, {
        status: response.status,
        data,
      })
    }

    return data as T
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    throw new ApiError(error instanceof Error ? error.message : 'Network request failed', {
      status: 0,
      data: error,
      isNetworkError: true,
    })
  } finally {
    window.clearTimeout(timeoutId)
  }
}
