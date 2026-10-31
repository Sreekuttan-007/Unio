import { AlertTriangle, ArrowRight, Boxes, Radar, Timer, UsersRound, Wrench } from 'lucide-react'
import { Badge, Banner, Button, Card, CardHeader, ImpactChain, ListRow, PageHeader, ProgressBar, StatTile, type ImpactStep } from '@/ui'
import type { Approval, ImpactReport, Incident, SlaRow, StockRow, TechnicianCard, WorkOrder } from '@/types/domain'
import { IncidentStatusBadge, PriorityBadge, SlaSummary } from '../shared/badges'
import { ago, money } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'
import { useNavTo } from '../shared/useNavTo'
import { SessionCard } from '../shell/SessionCard'

const OPEN = (incident: Incident) => !['RESOLVED', 'CLOSED'].includes(incident.status)

export function CommandCentreScreen() {
  const incidents = useApi<{ items: Incident[] }>('/incidents', { refetchMs: 8_000 })
  const technicians = useApi<TechnicianCard[]>('/technicians', { refetchMs: 8_000 })
  const orders = useApi<{ items: WorkOrder[] }>('/work-orders', { refetchMs: 8_000 })
  const sla = useApi<SlaRow[]>('/sla/instances', { refetchMs: 8_000 })
  const { go } = useNavTo()

  const open = (incidents.data?.items ?? []).filter(OPEN)
  const blocked = (orders.data?.items ?? []).filter((order) => order.status === 'BLOCKED')
  const flagged = (orders.data?.items ?? []).filter((order) => order.needsReassignment)
  const atRisk = (sla.data ?? []).filter((row) => ['AT_RISK', 'BREACHED'].includes(row.state))
  const lead = open.find((incident) => incident.priority === 'P1')
  const impact = useApi<ImpactReport>(`/cascading/impact/${lead?.id ?? 'none'}`, { enabled: !!lead })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Command Centre"
        eyebrow="Right now"
        description="Everything that needs a decision, in one place. Updates every few seconds."
      />

      {lead ? (
        <Banner
          tone="danger"
          role="alert"
          title={`Active disruption: ${lead.title}`}
          action={<Button variant="secondary" onClick={() => go('fac.simulator')}>Compare recovery plans</Button>}
        >
          {lead.impact.rooms} rooms, {lead.impact.sessions} sessions and {lead.impact.exams} exam affected, about {lead.impact.people} people. {blocked.length > 0 ? `${blocked.length} repair is blocked on a part.` : ''}
        </Banner>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile label="Open incidents" value={open.length} tone="accent" icon={<Radar aria-hidden="true" className="size-5" />} hint={`${open.filter((item) => item.priority === 'P1').length} are P1`} />
        <StatTile label="SLA at risk" value={atRisk.length} tone="warning" icon={<Timer aria-hidden="true" className="size-5" />} hint="Including breached" />
        <StatTile label="Work blocked" value={blocked.length} tone="danger" icon={<Boxes aria-hidden="true" className="size-5" />} hint="Waiting for parts" />
        <StatTile label="Needs reassignment" value={flagged.length} tone="warning" icon={<UsersRound aria-hidden="true" className="size-5" />} hint="Technician unavailable" />
        <StatTile label="Technicians free" value={(technicians.data ?? []).filter((tech) => tech.availability === 'AVAILABLE').length} tone="success" icon={<Wrench aria-hidden="true" className="size-5" />} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
        <Card>
          <CardHeader title="Incidents" action={<Button variant="ghost" compact onClick={() => go('fac.triage')}>Open triage</Button>} />
          <QueryBoundary query={incidents}>
            {(data) => [...data.items].filter(OPEN).sort((a, b) => a.priority.localeCompare(b.priority)).slice(0, 6).map((incident) => (
              <ListRow key={incident.id} onClick={() => go('fac.triage')} title={incident.title} subtitle={`${incident.id} · ${incident.reportCount} reports · ${incident.assignedTo ?? 'Unassigned'} · ${ago(incident.updatedAt)}`} trailing={<span className="flex items-center gap-1.5"><PriorityBadge priority={incident.priority} /><IncidentStatusBadge status={incident.status} /></span>} />
            ))}
          </QueryBoundary>
        </Card>
        <Card>
          <CardHeader title="Closest to breaching" description="SLA state, with the early warning" />
          <QueryBoundary query={sla}>
            {(rows) => [...rows].filter((row) => row.state !== 'PAUSED').sort((a, b) => b.percentElapsed - a.percentElapsed).slice(0, 4).map((row) => (
              <div key={row.id} className="border-b border-line px-4 py-3 last:border-0">
                <p className="mb-2 text-sm font-medium text-ink">{row.subject}</p>
                <SlaSummary sla={{ state: row.state, percentElapsed: row.percentElapsed, remaining: row.remaining, dueAt: '' }} compact />
              </div>
            ))}
          </QueryBoundary>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Why it is happening" description={lead ? `${lead.id} traced through stored relationships` : 'No P1 incident right now'} />
          <div className="px-5 py-4">
            {lead ? <QueryBoundary query={impact}>{(data) => <ImpactChain steps={data.chain.slice(0, 5) as ImpactStep[]} />}</QueryBoundary> : <p className="text-sm text-muted">Nothing is disrupting the campus.</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="Technician load" action={<Button variant="ghost" compact onClick={() => go('fac.technicians')}>Open board</Button>} />
          <QueryBoundary query={technicians}>
            {(items) => (
              <div className="space-y-4 px-5 py-4">
                {items.map((tech) => (
                  <div key={tech.id}>
                    <div className="mb-1 flex justify-between text-sm"><span className="font-medium text-ink">{tech.name}</span><Badge tone={tech.availability === 'SICK' ? 'danger' : tech.availability === 'AVAILABLE' ? 'success' : 'info'}>{tech.availability === 'SICK' ? 'Off sick' : tech.availability === 'AVAILABLE' ? 'Free' : 'Busy'}</Badge></div>
                    <ProgressBar value={tech.workloadPercent} tone={tech.workloadPercent > 80 ? 'danger' : tech.workloadPercent > 60 ? 'warning' : 'success'} />
                  </div>
                ))}
              </div>
            )}
          </QueryBoundary>
        </Card>
      </div>
      <SessionCard />
    </div>
  )
}
export function DeptOverviewScreen() {
  const incidents = useApi<{ items: Incident[] }>('/incidents', { refetchMs: 10_000 })
  const orders = useApi<{ items: WorkOrder[] }>('/work-orders')
  const sla = useApi<SlaRow[]>('/sla/instances')
  const stock = useApi<StockRow[]>('/inventory/items')
  const approvals = useApi<{ items: Approval[] }>('/approvals')
  const { go } = useNavTo()
  const open = (incidents.data?.items ?? []).filter(OPEN)
  const blocked = (orders.data?.items ?? []).filter((order) => order.status === 'BLOCKED')
  const waiting = (approvals.data?.items ?? []).filter((item) => ['SUBMITTED', 'UNDER_REVIEW'].includes(item.status))

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="Computer Science: what is open, what is at risk, and what you are waiting on."
      />
      {blocked.length > 0 ? (
        <Banner tone="warning" title={`${blocked.length} work order blocked on a part`} action={<Button variant="secondary" compact onClick={() => go('dept.approvals')}>See your request</Button>}>
          Your purchase request {blocked[0]?.approvalId} is waiting for a Procurement decision. You cannot approve it yourself.
        </Banner>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-4">
        <StatTile label="Open incidents" value={open.length} tone="accent" icon={<AlertTriangle aria-hidden="true" className="size-5" />} />
        <StatTile label="SLA at risk" value={(sla.data ?? []).filter((row) => ['AT_RISK', 'BREACHED'].includes(row.state)).length} tone="warning" />
        <StatTile label="Parts short" value={(stock.data ?? []).filter((row) => row.blockedWorkOrders > 0).length} tone="danger" />
        <StatTile label="Waiting on approval" value={waiting.length} hint={waiting[0] ? money(waiting.reduce((sum, item) => sum + item.amountPaise, 0)) : undefined} />
      </div>
      <Card>
        <CardHeader title="Department incidents" action={<Button variant="ghost" compact icon={<ArrowRight aria-hidden="true" className="size-4" />} onClick={() => go('dept.incidents')}>All</Button>} />
        <QueryBoundary query={incidents}>
          {(data) => data.items.filter(OPEN).map((incident) => <ListRow key={incident.id} title={incident.title} subtitle={`${incident.id} · ${incident.buildingName}`} trailing={<span className="flex items-center gap-1.5"><PriorityBadge priority={incident.priority} /><IncidentStatusBadge status={incident.status} /></span>} />)}
        </QueryBoundary>
      </Card>
      <SessionCard />
    </div>
  )
}

export function ProcOverviewScreen() {
  const approvals = useApi<{ items: Approval[] }>('/approvals')
  const invoices = useApi<{ id: string; status: string; discrepancies: { resolved: boolean }[] }[]>('/invoices')
  const receipts = useApi<{ id: string; status: string }[]>('/goods-receipts')
  const { go } = useNavTo()
  const waiting = (approvals.data?.items ?? []).filter((item) => ['SUBMITTED', 'UNDER_REVIEW'].includes(item.status))
  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description="What is waiting for your decision, and what is waiting to be received."
      />
      <div className="grid gap-4 sm:grid-cols-4">
        <StatTile label="Waiting for decision" value={waiting.length} tone="warning" />
        <StatTile label="Value waiting" value={money(waiting.reduce((sum, item) => sum + item.amountPaise, 0))} tone="accent" />
        <StatTile label="Invoice discrepancies" value={(invoices.data ?? []).filter((item) => item.status === 'DISCREPANCY').length} tone="danger" />
        <StatTile label="Receipts to post" value={(receipts.data ?? []).filter((item) => item.status === 'PENDING').length} tone="info" />
      </div>
      <Card>
        <CardHeader title="Next to decide" action={<Button variant="ghost" compact onClick={() => go('proc.queue')}>Open queue</Button>} />
        <QueryBoundary query={approvals} isEmpty={() => waiting.length === 0} emptyTitle="Nothing waiting">
          {() => waiting.map((item) => <ListRow key={item.id} title={item.title} subtitle={`${item.id} · ${item.requesterName}`} meta={money(item.amountPaise)} />)}
        </QueryBoundary>
      </Card>
      <SessionCard />
    </div>
  )
}
