import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { api, newId } from '@/platform/api/client'

interface Options {
  query?: Record<string, string | number | boolean | undefined>
  enabled?: boolean
  /** Poll every this many ms, for screens that should feel live. */
  refetchMs?: number
}

/** One read hook for every screen. The key is the path, so a write can refresh it by path. */
export function useApi<T>(path: string, options: Options = {}) {
  return useQuery({
    queryKey: [path, options.query ?? null],
    queryFn: () => api<T>(path, { query: options.query }),
    enabled: options.enabled ?? true,
    refetchInterval: options.refetchMs,
  })
}

/** A short, stable fingerprint of a request body (FNV-1a), so the same body gives the same key. */
function fingerprint(body: unknown): string {
  const text = JSON.stringify(body) ?? ''
  let hash = 0x811c9dc5
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash.toString(16)
}

/**
 * A write that refreshes the listed read paths when it succeeds.
 *
 * With `idempotent`, retrying the same body reuses one Idempotency-Key, so a timeout followed by a
 * second tap applies once. Changing the body gives a new key, and so does a success, so the next
 * report from the same screen is a new request.
 */
export function useAction<TBody, TResult = unknown>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string | ((body: TBody) => string),
  refresh: string[] = [],
  options: { idempotent?: boolean } = {},
) {
  const queryClient = useQueryClient()
  const draft = useRef(newId())
  return useMutation({
    mutationFn: (body: TBody) =>
      api<TResult>(typeof path === 'function' ? path(body) : path, {
        method,
        body: body as unknown,
        idempotencyKey: options.idempotent ? `${draft.current}-${fingerprint(body)}` : undefined,
      }),
    onSuccess: async () => {
      draft.current = newId()
      await Promise.all(refresh.map((key) => queryClient.invalidateQueries({ predicate: (query) => String(query.queryKey[0]).startsWith(key) })))
    },
  })
}
