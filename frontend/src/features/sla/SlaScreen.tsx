import { Badge, Card, DataTable, PageHeader, SlaMeter, StatTile, type Column } from '@/ui'
import type { SlaRow } from '@/types/domain'
import { PriorityBadge } from '../shared/badges'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

interface Summary {
  onTrack: number
  atRisk: number
  breached: number
  paused: number
  compliance: number
}

export function SlaScreen({ title, description }: { title: string; description: string }) {
  const rows = useApi<SlaRow[]>('/sla/instances', { refetchMs: 10_000 })
  const summary = useApi<Summary>('/sla/summary')

  const columns: Column<SlaRow>[] = [
    { key: 'subject', header: 'Work', cell: (row) => (<div><p className="font-medium">{row.subject}</p><p className="text-xs text-muted">{row.owner ?? 'Unassigned'}</p></div>) },
    { key: 'priority', header: 'Priority', cell: (row) => <PriorityBadge priority={row.priority} /> },
    { key: 'sla', header: 'SLA', cell: (row) => <SlaMeter percent={row.percentElapsed} state={row.state} remaining={row.remaining} size="sm" /> },
    { key: 'esc', header: 'Escalation', cell: (row) => (row.escalationLevel > 0 ? <Badge tone="danger">Level {row.escalationLevel}</Badge> : <span className="text-muted">None</span>) },
    { key: 'risk', header: 'Early warning', cell: (row) => (row.risk ? <span className="text-sm"><span className="font-medium">{Math.round(row.risk.probability * 100)}% likely to breach.</span> <span className="text-muted">{row.risk.factor}</span></span> : <span className="text-muted">None</span>) },
  ]

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} />
      <QueryBoundary query={summary}>
        {(data) => (
          <div className="grid gap-4 sm:grid-cols-5">
            <StatTile label="Compliance" value={`${data.compliance}%`} tone="accent" />
            <StatTile label="On track" value={data.onTrack} tone="success" />
            <StatTile label="At risk" value={data.atRisk} tone="warning" />
            <StatTile label="Breached" value={data.breached} tone="danger" />
            <StatTile label="Paused" value={data.paused} tone="info" />
          </div>
        )}
      </QueryBoundary>
      <QueryBoundary query={rows} isEmpty={(items) => items.length === 0} emptyTitle="Nothing is being timed">
        {(items) => <Card><DataTable caption={title} columns={columns} rows={[...items].sort((a, b) => b.percentElapsed - a.percentElapsed)} rowKey={(row) => row.id} /></Card>}
      </QueryBoundary>
    </div>
  )
}
