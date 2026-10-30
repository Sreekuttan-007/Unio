import { API_ORIGIN, API_PREFIX } from './config'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  readonly correlationId: string | null

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}, correlationId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.correlationId = correlationId
  }

  /** Status 0 means the request never got an answer: offline, blocked, or a sleeping host. */
  get isNetwork(): boolean {
    return this.status === 0
  }
}

interface ApiConfig {
  getToken: () => string | null
  /** Called when a request made with a token comes back 401, so the session can be cleared. */
  onUnauthorized: () => void
}

let config: ApiConfig = { getToken: () => null, onUnauthorized: () => {} }

export function configureApi(next: ApiConfig): void {
  config = next
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
  /** Pass a stable key per user action so a retried or double-tapped write runs once on the server. */
  idempotencyKey?: string
  /** false for public endpoints such as login. */
  auth?: boolean
  signal?: AbortSignal
  timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 20_000

export function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(`${API_ORIGIN}${API_PREFIX}${path}`)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value))
  }
  return url.toString()
}

function parseErrorBody(status: number, text: string): ApiError {
  try {
    const body = JSON.parse(text) as Partial<{ code: string; message: string; details: Record<string, unknown>; correlationId: string | null }>
    if (body && typeof body.code === 'string' && typeof body.message === 'string') {
      return new ApiError(status, body.code, body.message, body.details ?? {}, body.correlationId ?? null)
    }
  } catch {
    // not our error shape, fall through to the generic message
  }
  return new ApiError(status, 'HTTP_ERROR', `The server answered ${status}.`)
}

export async function api<T = void>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, idempotencyKey, auth = true, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options
  const token = auth ? config.getToken() : null
  const headers: Record<string, string> = { Accept: 'application/json', 'X-Correlation-Id': newId() }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  signal?.addEventListener('abort', () => controller.abort(), { once: true })

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'Cannot reach the server. Check your connection and try again.')
  } finally {
    clearTimeout(timer)
  }

  if (response.status === 204) return undefined as T
  const text = await response.text()
  if (!response.ok) {
    const error = parseErrorBody(response.status, text)
    if (response.status === 401 && token) config.onUnauthorized()
    throw error
  }
  return (text ? JSON.parse(text) : undefined) as T
}
