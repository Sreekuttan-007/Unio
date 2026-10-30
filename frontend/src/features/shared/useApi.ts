import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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

/** A write that refreshes the listed read paths when it succeeds. */
export function useAction<TBody, TResult = unknown>(
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string | ((body: TBody) => string),
  refresh: string[] = [],
  options: { idempotent?: boolean } = {},
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: TBody) => api<TResult>(typeof path === 'function' ? path(body) : path, { method, body: body as unknown, idempotencyKey: options.idempotent ? newId() : undefined }),
    onSuccess: async () => {
      await Promise.all(refresh.map((key) => queryClient.invalidateQueries({ predicate: (query) => String(query.queryKey[0]).startsWith(key) })))
    },
  })
}
