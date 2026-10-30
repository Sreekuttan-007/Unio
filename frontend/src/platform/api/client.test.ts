import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { server } from '@/test/setup'
import { api, ApiError, configureApi } from './client'
import { API_ORIGIN, API_PREFIX } from './config'

const url = (path: string) => `${API_ORIGIN}${API_PREFIX}${path}`

afterEach(() => configureApi({ getToken: () => null, onUnauthorized: () => {} }))

describe('api client', () => {
  it('sends the bearer token and a correlation id, and returns parsed JSON', async () => {
    configureApi({ getToken: () => 'mock.STUDENT', onUnauthorized: () => {} })
    let seen: Headers | undefined
    server.use(
      http.get(url('/thing'), ({ request }) => {
        seen = request.headers
        return HttpResponse.json({ ok: true })
      }),
    )
    expect(await api<{ ok: boolean }>('/thing')).toEqual({ ok: true })
    expect(seen?.get('authorization')).toBe('Bearer mock.STUDENT')
    expect(seen?.get('x-correlation-id')).toMatch(/.{8,}/)
  })

  it('does not send the token to public endpoints', async () => {
    configureApi({ getToken: () => 'mock.STUDENT', onUnauthorized: () => {} })
    let authorization: string | null = 'unset'
    server.use(
      http.post(url('/auth/login'), ({ request }) => {
        authorization = request.headers.get('authorization')
        return HttpResponse.json({})
      }),
    )
    await api('/auth/login', { method: 'POST', body: {}, auth: false })
    expect(authorization).toBeNull()
  })

  it('sends an idempotency key only when asked', async () => {
    const keys: (string | null)[] = []
    server.use(
      http.post(url('/things'), ({ request }) => {
        keys.push(request.headers.get('idempotency-key'))
        return HttpResponse.json({})
      }),
    )
    await api('/things', { method: 'POST', body: {}, idempotencyKey: 'once-only-0001' })
    await api('/things', { method: 'POST', body: {} })
    expect(keys).toEqual(['once-only-0001', null])
  })

  it('turns the standard error body into an ApiError', async () => {
    server.use(
      http.get(url('/boom'), () =>
        HttpResponse.json({ code: 'ROOM_OVERLAP', message: 'Room A204 is booked.', details: { room: 'A204' }, correlationId: 'abc-123456' }, { status: 422 }),
      ),
    )
    const error = await api('/boom').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 422, code: 'ROOM_OVERLAP', message: 'Room A204 is booked.', correlationId: 'abc-123456' })
    expect((error as ApiError).details).toEqual({ room: 'A204' })
  })

  it('falls back to a generic error when the body is not ours', async () => {
    server.use(http.get(url('/html'), () => new HttpResponse('<html>bad gateway</html>', { status: 502 })))
    await expect(api('/html')).rejects.toMatchObject({ status: 502, code: 'HTTP_ERROR' })
  })

  it('reports an unreachable server as status 0', async () => {
    server.use(http.get(url('/down'), () => HttpResponse.error()))
    const error = await api('/down').catch((caught: unknown) => caught)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).isNetwork).toBe(true)
  })

  it('clears the session on a 401, but only when a token was sent', async () => {
    const onUnauthorized = vi.fn()
    configureApi({ getToken: () => 'mock.STUDENT', onUnauthorized })
    server.use(http.get(url('/private'), () => HttpResponse.json({ code: 'UNAUTHENTICATED', message: 'No.', details: {}, correlationId: null }, { status: 401 })))
    await expect(api('/private')).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)

    await expect(api('/private', { auth: false })).rejects.toMatchObject({ status: 401 })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('returns undefined for 204', async () => {
    server.use(http.post(url('/empty'), () => new HttpResponse(null, { status: 204 })))
    expect(await api('/empty', { method: 'POST' })).toBeUndefined()
  })

  it('serialises query parameters and skips undefined ones', async () => {
    let search = ''
    server.use(
      http.get(url('/list'), ({ request }) => {
        search = new URL(request.url).search
        return HttpResponse.json([])
      }),
    )
    await api('/list', { query: { page: 2, size: 20, filter: undefined } })
    expect(search).toBe('?page=2&size=20')
  })
})
