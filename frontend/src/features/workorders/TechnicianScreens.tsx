import { MapPin, ShieldAlert } from 'lucide-react'
import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, CardHeader, Dropzone, ListRow, PageHeader, SegmentedControl, SelectField, Sheet, TextArea } from '@/ui'
import type { TechnicianCard, WorkOrder } from '@/types/domain'
import { PriorityBadge, SlaSummary, WorkOrderStatusBadge } from '../shared/badges'
import { describeError } from '../shared/errors'
import { dateTime, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'
import { SessionCard } from '../shell/SessionCard'

const PART_TONE = { RESERVED: 'success', SHORT: 'danger', ISSUED: 'neutral' } as const

type Pending = { order: WorkOrder; action: 'block' | 'complete' } | null

function TaskCard({ order, onAct, onSheet, busy }: { order: WorkOrder; onAct: (key: string) => void; onSheet: (action: 'block' | 'complete') => void; busy: boolean }) {
  return (
    <Card data-testid={`task-${order.id}`} className={order.status === 'BLOCKED' ? 'border-danger' : undefined}>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <PriorityBadge priority={order.priority} />
          <WorkOrderStatusBadge status={order.status} />
          <span className="text-xs text-muted">{order.id}</span>
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">{order.title}</h2>
          <p className="mt-1 flex items-start gap-1.5 text-sm text-muted"><MapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0" />{order.location}</p>
        </div>
        <SlaSummary sla={order.sla} />
        {order.safetyNote ? <Banner tone="warning" title="Safety"><span className="flex gap-2"><ShieldAlert aria-hidden="true" className="size-4 shrink-0" />{order.safetyNote}</span></Banner> : null}
        {order.status === 'BLOCKED' ? <Banner tone="danger" title="Waiting for a part" role="status">The part is out of stock. Purchase request {order.approvalId ?? ''} is with Procurement, and you will be told when it arrives.</Banner> : null}
        {order.needsReassignment ? <Banner tone="warning" title="Reassignment requested">{order.needsReassignment.reason}</Banner> : null}
        {order.parts.length > 0 ? (
          <ul className="space-y-1.5 text-sm">
            {order.parts.map((part) => (
              <li key={part.sku} className="flex items-center justify-between gap-2">
                <span className="text-ink">{part.qty} x {part.name}</span>
                <Badge tone={PART_TONE[part.state]}>{part.state === 'SHORT' ? 'Short' : part.state === 'RESERVED' ? 'Reserved' : 'Issued'}</Badge>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="flex flex-wrap gap-2">
          {order.availableActions.map((action) => {
            const key = action.key.replace('workorder.', '')
            const sheet = key === 'block' || key === 'complete'
            return (
              <Button key={action.key} variant={key === 'complete' || key === 'start' || key === 'accept' ? 'primary' : 'secondary'} loading={busy} className="flex-1 sm:flex-none" onClick={() => (sheet ? onSheet(key as 'block' | 'complete') : onAct(key))}>
                {action.label}
              </Button>
            )
          })}
        </div>
        {order.unavailableActions.map((action) => <p key={action.key} className="text-xs text-muted">{action.label} is unavailable. {action.reason}</p>)}
      </CardBody>
    </Card>
  )
}

export function MyTasksScreen() {
  const orders = useApi<{ items: WorkOrder[] }>('/work-orders', { refetchMs: 8_000 })
  const act = useAction<{ id: string; action: string; body?: Record<string, unknown> }, WorkOrder>('POST', (job) => `/work-orders/${job.id}/${job.action}`, ['/work-orders', '/inventory'])
  const [pending, setPending] = useState<Pending>(null)
  const [notes, setNotes] = useState('')
  const [reason, setReason] = useState('WAITING_FOR_PARTS')
  const [photos, setPhotos] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)

  const run = async (id: string, action: string, body?: Record<string, unknown>) => {
    setError(null)
    try {
      await act.mutateAsync({ id, action, body })
      setPending(null)
      setNotes('')
      setPhotos([])
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="My Tasks" description="Most urgent first. Everything here works one-handed." />
      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}
      <QueryBoundary query={orders} isEmpty={(data) => data.items.length === 0} emptyTitle="No tasks" emptyDescription="New work shows up here the moment it is assigned to you.">
        {(data) => {
          const rank: Record<WorkOrder['status'], number> = { IN_PROGRESS: 0, ACCEPTED: 1, ASSIGNED: 2, BLOCKED: 3, PENDING_ASSIGNMENT: 4, COMPLETED: 5, VERIFIED: 6 }
          const sorted = [...data.items].sort((a, b) => a.priority.localeCompare(b.priority) || rank[a.status] - rank[b.status])
          return (
            <div className="space-y-4">
              {sorted.map((order) => (
                <TaskCard key={order.id} order={order} busy={act.isPending} onAct={(key) => void run(order.id, key)} onSheet={(action) => { setError(null); setPending({ order, action }) }} />
              ))}
            </div>
          )
        }}
      </QueryBoundary>

      <Sheet open={pending?.action === 'complete'} title={`Complete ${pending?.order.id ?? ''}`} onClose={() => setPending(null)}>
        <div className="space-y-4">
          <TextArea label="What did you do" value={notes} onChange={(event) => setNotes(event.target.value)} hint="Required. Short is fine." />
          <Dropzone label="Add a completion photo" hint={photos.length ? photos.map((file) => file.name).join(', ') : 'Use the camera'} accept="image/*" capture onFiles={setPhotos} />
          <Button className="w-full" loading={act.isPending} disabled={!notes.trim()} onClick={() => pending && void run(pending.order.id, 'complete', { notes })}>Mark complete</Button>
        </div>
      </Sheet>

      <Sheet open={pending?.action === 'block'} title={`Report a blocker on ${pending?.order.id ?? ''}`} onClose={() => setPending(null)}>
        <div className="space-y-4">
          <SelectField label="What is stopping you" value={reason} onChange={(event) => setReason(event.target.value)} options={[{ value: 'WAITING_FOR_PARTS', label: 'A part is missing' }, { value: 'ACCESS', label: 'I cannot get access' }, { value: 'SKILL_MISMATCH', label: 'This needs a different skill' }]} />
          <TextArea label="Details" value={notes} onChange={(event) => setNotes(event.target.value)} />
          <Button className="w-full" variant="danger" loading={act.isPending} onClick={() => pending && void run(pending.order.id, 'block', { reason, notes })}>Block this task</Button>
        </div>
      </Sheet>
      <SessionCard />
    </div>
  )
}

interface MinePart {
  sku: string
  name: string
  qty: number
  state: 'RESERVED' | 'SHORT' | 'ISSUED'
  available: number
  workOrderId: string
  workOrderTitle: string
}

export function MyPartsScreen() {
  const parts = useApi<MinePart[]>('/inventory/mine', { refetchMs: 15_000 })
  return (
    <div className="space-y-5">
      <PageHeader title="Parts" description="Parts reserved for your tasks. You ask for parts and never change stock yourself." />
      <QueryBoundary query={parts} isEmpty={(items) => items.length === 0} emptyTitle="No parts reserved">
        {(items) => (
          <Card>
            {items.map((part) => (
              <ListRow
                key={`${part.workOrderId}-${part.sku}`}
                title={`${part.qty} x ${part.name}`}
                subtitle={`${part.workOrderId} · ${part.workOrderTitle}`}
                trailing={<Badge tone={PART_TONE[part.state]}>{part.state === 'SHORT' ? 'Out of stock' : part.state === 'RESERVED' ? `Reserved, ${part.available} in stock` : 'Issued to you'}</Badge>}
              />
            ))}
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}

interface Me extends TechnicianCard {
  leave: { from: string; to: string; reason: string }[]
}

export function AvailabilityScreen() {
  const me = useApi<Me>('/technicians/me')
  const update = useAction<{ availability: TechnicianCard['availability'] }, { availability: string; flaggedWorkOrders: number }>('PATCH', '/technicians/me/availability', ['/technicians', '/work-orders'])
  const [flagged, setFlagged] = useState<number | null>(null)

  const choose = async (availability: TechnicianCard['availability']) => {
    const result = await update.mutateAsync({ availability })
    setFlagged(result.flaggedWorkOrders)
  }

  return (
    <div className="space-y-5">
      <PageHeader title="Availability" description="Tell the team when you cannot work. Your open tasks are flagged so a replacement can be found." />
      <QueryBoundary query={me}>
        {(profile) => (
          <>
            {flagged ? <Banner tone="warning" title={`${flagged} open ${flagged === 1 ? 'task was' : 'tasks were'} flagged for reassignment`} role="status">Facilities can see them now and will pick a qualified replacement.</Banner> : null}
            <Card>
              <CardHeader title="Right now" />
              <CardBody className="space-y-4">
                <SegmentedControl<TechnicianCard['availability']>
                  label="Availability"
                  value={profile.availability === 'BUSY' ? 'AVAILABLE' : profile.availability}
                  onChange={(value) => void choose(value)}
                  options={[{ value: 'AVAILABLE', label: 'Available' }, { value: 'SICK', label: 'Sick' }, { value: 'ON_LEAVE', label: 'On leave' }]}
                />
                <p className="text-sm text-muted">Today's shift: <span className="font-medium text-ink">{profile.shift}</span></p>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="My skills" />
              <CardBody className="flex flex-wrap gap-2">{profile.skills.map((skill) => <Badge key={skill.code} tone="accent">{titleCase(skill.code)} level {skill.level}</Badge>)}</CardBody>
            </Card>
            <Card>
              <CardHeader title="Planned leave" />
              {profile.leave.map((item) => <ListRow key={item.from} title={`${item.from} to ${item.to}`} subtitle={item.reason} />)}
            </Card>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}

interface HistoryRow {
  id: string
  summary: string
  roomId: string | null
  category: string
  completedAt: string
}

export function MaintenanceHistoryScreen() {
  const history = useApi<HistoryRow[]>('/maintenance-history')
  return (
    <div>
      <PageHeader title="History" description="Maintenance you have completed." />
      <QueryBoundary query={history} isEmpty={(items) => items.length === 0} emptyTitle="Nothing completed yet">
        {(items) => (
          <Card>
            {items.map((item) => <ListRow key={item.id} title={item.summary} subtitle={`${item.roomId ?? 'Campus'} · ${titleCase(item.category)}`} meta={dateTime(item.completedAt)} />)}
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}
