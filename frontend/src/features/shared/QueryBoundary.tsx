import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { EmptyState, ErrorState, OfflineState, ScreenSkeleton } from '@/ui'
import { ApiError } from '@/platform/api/client'
import { describeError } from './errors'

/** Loading, error and empty states in one place, so every screen handles all three the same way. */
export function QueryBoundary<T>({
  query,
  children,
  isEmpty,
  emptyTitle = 'Nothing here yet',
  emptyDescription,
}: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
  isEmpty?: (data: T) => boolean
  emptyTitle?: string
  emptyDescription?: string
}) {
  if (query.isPending) return <ScreenSkeleton />
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.isNetwork) return <OfflineState onRetry={() => void query.refetch()} />
    return <ErrorState description={describeError(query.error)} onRetry={() => void query.refetch()} />
  }
  if (isEmpty?.(query.data)) return <EmptyState title={emptyTitle} description={emptyDescription} />
  return <>{children(query.data)}</>
}
