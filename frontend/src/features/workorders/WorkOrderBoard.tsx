import { useState } from 'react'
import { Badge, Kanban, PageHeader } from '@/ui'
import type { WorkOrder } from '@/types/domain'
import { useAuth } from '@/platform/auth/AuthProvider'
import { PriorityBadge, SlaSummary } from '../shared/badges'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'
import { WorkOrderSheet } from './WorkOrderSheet'

function Card({ order, onOpen }: { order: WorkOrder; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} data-testid={`wo-${order.id}`} className="w-full rounded-md border border-line bg-surface p-3 text-left shadow-card hover:border-accent">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-muted">{order.id}</span>
        <PriorityBadge priority={order.priority} />
      </div>
      <p className="text-sm font-medium text-ink">{order.title}</p>
      <p className="mt-1 text-xs text-muted">{order.assignedTechnicianName ?? 'Unassigned'}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {order.parts.some((part) => part.state === 'SHORT') ? <Badge tone="danger">Part short</Badge> : null}
        {order.needsReassignment ? <Badge tone="warning">Reassign</Badge> : null}
      </div>
      <div className="mt-3"><SlaSummary sla={order.sla} compact /></div>
    </button>
  )
}

export function WorkOrderBoard({ title, description }: { title: string; description: string }) {
  const orders = useApi<{ items: WorkOrder[] }>('/work-orders', { refetchMs: 10_000 })
  const { bootstrap } = useAuth()
  const [openId, setOpenId] = useState<string | null>(null)
  const canAssign = !!bootstrap?.permissions.some((key) => key.startsWith('workorder.assign'))

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} />
      <QueryBoundary query={orders} isEmpty={(data) => data.items.length === 0} emptyTitle="No work orders">
        {(data) => {
          const col = (statuses: WorkOrder['status'][]) => data.items.filter((order) => statuses.includes(order.status)).map((order) => ({ id: order.id, node: <Card order={order} onOpen={() => setOpenId(order.id)} /> }))
          return (
            <>
              <Kanban
                columns={[
                  { id: 'new', title: 'Needs assignment', cards: col(['PENDING_ASSIGNMENT']) },
                  { id: 'assigned', title: 'Assigned', cards: col(['ASSIGNED', 'ACCEPTED']) },
                  { id: 'doing', title: 'In progress', cards: col(['IN_PROGRESS']) },
                  { id: 'blocked', title: 'Blocked', cards: col(['BLOCKED']) },
                  { id: 'done', title: 'Done', cards: col(['COMPLETED', 'VERIFIED']) },
                ]}
              />
              <WorkOrderSheet order={data.items.find((order) => order.id === openId)} onClose={() => setOpenId(null)} canAssign={canAssign} />
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}
