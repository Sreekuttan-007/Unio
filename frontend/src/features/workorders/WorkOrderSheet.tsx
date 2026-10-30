import { Banner, Badge, Card, CardBody, ListRow, Sheet } from '@/ui'
import type { WorkOrder } from '@/types/domain'
import { CategoryBadge, PriorityBadge, SlaSummary, WorkOrderStatusBadge } from '../shared/badges'
import { money } from '../shared/format'
import { AssignPanel } from './AssignPanel'

const PART_TONE = { RESERVED: 'success', SHORT: 'danger', ISSUED: 'neutral' } as const

export function WorkOrderSheet({ order, onClose, canAssign }: { order: WorkOrder | undefined; onClose: () => void; canAssign: boolean }) {
  return (
    <Sheet open={!!order} title={order ? `${order.id} · ${order.title}` : ''} onClose={onClose}>
      {order ? (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <PriorityBadge priority={order.priority} />
            <WorkOrderStatusBadge status={order.status} />
            <CategoryBadge category={order.category} />
            <Badge>Incident {order.incidentId}</Badge>
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-xs text-muted">Where</dt><dd>{order.location}</dd></div>
            <div><dt className="text-xs text-muted">Asset</dt><dd>{order.asset ?? 'None'}</dd></div>
            <div><dt className="text-xs text-muted">Technician</dt><dd>{order.assignedTechnicianName ?? 'Nobody yet'}</dd></div>
            <div><dt className="text-xs text-muted">Needs</dt><dd>{order.requiredSkills.map((skill) => `${skill.code} level ${skill.minLevel}+`).join(', ')}</dd></div>
          </dl>
          <SlaSummary sla={order.sla} />
          {order.blockReason ? <Banner tone="danger" title="Blocked on parts">The part is out of stock, so the work cannot continue until it arrives.{order.approvalId ? ` Purchase request ${order.approvalId} is waiting for approval.` : ''}</Banner> : null}
          {order.needsReassignment ? <Banner tone="warning" title="Needs a new technician">{order.needsReassignment.reason}. Suggested: {order.needsReassignment.suggestedName}.</Banner> : null}
          {order.parts.length > 0 ? (
            <Card>
              <CardBody className="p-0">
                {order.parts.map((part) => (
                  <ListRow key={part.sku} title={`${part.qty} x ${part.name}`} subtitle={`${part.available} available`} trailing={<Badge tone={PART_TONE[part.state]}>{part.state === 'SHORT' ? 'Short' : part.state === 'RESERVED' ? 'Reserved' : 'Issued'}</Badge>} />
                ))}
              </CardBody>
            </Card>
          ) : null}
          {canAssign && ['PENDING_ASSIGNMENT', 'ASSIGNED'].includes(order.status) ? <AssignPanel order={order} /> : null}
          <p className="text-xs text-muted">Estimated {order.estimatedMinutes} minutes · {money(0)} approved spend</p>
        </div>
      ) : null}
    </Sheet>
  )
}
