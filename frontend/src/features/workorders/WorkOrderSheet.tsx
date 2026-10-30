import { useState } from 'react'
import { Banner, Badge, Button, Card, CardBody, ListRow, Sheet, TextArea } from '@/ui'
import type { WorkOrder } from '@/types/domain'
import { CategoryBadge, PriorityBadge, SlaSummary, WorkOrderStatusBadge } from '../shared/badges'
import { describeError } from '../shared/errors'
import { money } from '../shared/format'
import { useAction } from '../shared/useApi'
import { AssignPanel } from './AssignPanel'

const PART_TONE = { RESERVED: 'success', SHORT: 'danger', ISSUED: 'neutral' } as const

/** Verify or send back completed work. Shown only when the backend offers it. */
function VerifyPanel({ order }: { order: WorkOrder }) {
  const act = useAction<{ action: 'verify' | 'reject'; notes?: string }, WorkOrder>('POST', (job) => `/work-orders/${order.id}/${job.action}`, ['/work-orders'])
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string | null>(null)
  const offered = (key: string) => order.availableActions.some((item) => item.key === key)
  if (!offered('workorder.verify') && !offered('workorder.reject')) return null
  const run = async (action: 'verify' | 'reject') => {
    setError(null)
    try {
      await act.mutateAsync({ action, notes: notes.trim() || undefined })
    } catch (failure) {
      setError(describeError(failure))
    }
  }
  return (
    <section aria-label="Check the repair" className="space-y-3">
      <h3 className="text-sm font-semibold text-ink">Check the repair</h3>
      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}
      <TextArea label="Notes" value={notes} onChange={(event) => setNotes(event.target.value)} hint="Say what is still wrong if you send it back." />
      <div className="flex flex-wrap gap-2">
        {offered('workorder.verify') ? <Button loading={act.isPending} onClick={() => void run('verify')}>Verify the repair</Button> : null}
        {offered('workorder.reject') ? <Button variant="secondary" loading={act.isPending} onClick={() => void run('reject')}>Send back</Button> : null}
      </div>
    </section>
  )
}

const BLOCKED = { WAITING_FOR_PARTS: 'Blocked on parts', ACCESS: 'Blocked: no access', SKILL_MISMATCH: 'Blocked: needs a different skill' } as const

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
          {order.blockReason ? (
            <Banner tone="danger" title={BLOCKED[order.blockReason]}>
              {order.blockReason === 'WAITING_FOR_PARTS' ? `The part is out of stock, so the work cannot continue until it arrives.${order.approvalId ? ` Purchase request ${order.approvalId} is waiting for approval.` : ''}` : 'The technician cannot continue until this is sorted out.'}
            </Banner>
          ) : null}
          {order.needsReassignment ? <Banner tone="warning" title="Needs a new technician">{order.needsReassignment.reason}. {order.needsReassignment.suggestedName ? `Suggested: ${order.needsReassignment.suggestedName}.` : 'Nobody qualified is free right now.'}</Banner> : null}
          {order.parts.length > 0 ? (
            <Card>
              <CardBody className="p-0">
                {order.parts.map((part) => (
                  <ListRow key={part.sku} title={`${part.qty} x ${part.name}`} subtitle={`${part.available} available`} trailing={<Badge tone={PART_TONE[part.state]}>{part.state === 'SHORT' ? 'Short' : part.state === 'RESERVED' ? 'Reserved' : 'Issued'}</Badge>} />
                ))}
              </CardBody>
            </Card>
          ) : null}
          {canAssign && order.availableActions.some((item) => item.key === 'workorder.assign') ? <AssignPanel order={order} /> : null}
          <VerifyPanel order={order} />
          <p className="text-xs text-muted">Estimated {order.estimatedMinutes} minutes · {money(0)} approved spend</p>
        </div>
      ) : null}
    </Sheet>
  )
}
