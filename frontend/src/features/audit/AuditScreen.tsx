import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/platform/api/client'
import type { AuditEntry, AuditPage } from '@/platform/api/types'
import { Badge, Button, Card, DataTable, EmptyState, ErrorState, PageHeader, ScreenSkeleton, type Column } from '@/ui'
import { describeError } from '../shared/errors'

const PAGE_SIZE = 15

const COLUMNS: Column<AuditEntry>[] = [
  { key: 'at', header: 'When', cell: (row) => new Date(row.at).toLocaleString() },
  { key: 'action', header: 'Action', cell: (row) => <span className="font-medium">{row.action}</span> },
  { key: 'entity', header: 'Record', cell: (row) => `${row.entityType} ${row.entityId}` },
  { key: 'actor', header: 'By', cell: (row) => <Badge tone="neutral">{row.actorRole}</Badge> },
  { key: 'reason', header: 'Reason', cell: (row) => row.reason ?? 'None given' },
]

/** One audit screen for every role that may read audit. The server decides which entries come back. */
export function AuditScreen({ title, description }: { title: string; description: string }) {
  const [page, setPage] = useState(0)
  const audit = useQuery({
    queryKey: ['audit', page],
    queryFn: () => api<AuditPage>('/audit', { query: { page, size: PAGE_SIZE } }),
    refetchInterval: 20_000,
  })

  return (
    <div>
      <PageHeader title={title} description={description} />
      {audit.isPending ? <ScreenSkeleton /> : null}
      {audit.isError ? <ErrorState description={describeError(audit.error)} onRetry={() => void audit.refetch()} /> : null}
      {audit.data && audit.data.items.length === 0 ? (
        <EmptyState title="Nothing recorded yet" description="Approvals, overrides, role changes and stock movements show up here." />
      ) : null}
      {audit.data && audit.data.items.length > 0 ? (
        <Card>
          <DataTable columns={COLUMNS} rows={audit.data.items} rowKey={(row) => row.id} caption={title} />
          <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm text-muted">
            <span>
              {audit.data.total} entries, page {audit.data.page + 1} of {Math.max(1, Math.ceil(audit.data.total / PAGE_SIZE))}
            </span>
            <span className="flex gap-2">
              <Button variant="secondary" compact disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Newer</Button>
              <Button variant="secondary" compact disabled={(page + 1) * PAGE_SIZE >= audit.data.total} onClick={() => setPage((value) => value + 1)}>Older</Button>
            </span>
          </div>
        </Card>
      ) : null}
    </div>
  )
}
