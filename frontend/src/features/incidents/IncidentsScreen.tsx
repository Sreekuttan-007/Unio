import { Link2, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, ImpactChain, ListRow, PageHeader, SegmentedControl, Sheet, StatTile, Timeline, type ImpactStep } from '@/ui'
import type { ImpactReport, Incident } from '@/types/domain'
import { CategoryBadge, IncidentStatusBadge, PriorityBadge, SlaSummary } from '../shared/badges'
import { describeError } from '../shared/errors'
import { ago } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

type Filter = 'all' | 'open' | 'p1'

function IncidentDetail({ incident }: { incident: Incident }) {
  const impact = useApi<ImpactReport>(`/cascading/impact/${incident.id}`)
  const act = useAction<{ key: string }, { message: string }>('POST', (body) => `/incidents/${incident.id}/actions/${body.key}`, ['/incidents'])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async (key: string) => {
    setError(null)
    try {
      setMessage((await act.mutateAsync({ key })).message)
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        <PriorityBadge priority={incident.priority} />
        <IncidentStatusBadge status={incident.status} />
        <CategoryBadge category={incident.category} />
        {incident.relatedIds.map((id) => <Badge key={id} tone="info" icon={<Link2 aria-hidden="true" className="size-3" />}>Linked to {id}</Badge>)}
      </div>

      <Card>
        <CardBody className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-ink">Summary</h3>
            <Badge tone={incident.summary.source === 'AI' ? 'accent' : 'neutral'} icon={<Sparkles aria-hidden="true" className="size-3" />}>
              {incident.summary.source === 'AI' ? 'Written by AI' : 'Template'} from {incident.summary.basedOnReportCount} {incident.summary.basedOnReportCount === 1 ? 'report' : 'reports'}
            </Badge>
          </div>
          <p className="text-sm text-ink">{incident.summary.text}</p>
        </CardBody>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Rooms" value={incident.impact.rooms} />
        <StatTile label="Sessions" value={incident.impact.sessions} />
        <StatTile label="Exams" value={incident.impact.exams} tone={incident.impact.exams ? 'danger' : 'neutral'} />
        <StatTile label="People" value={incident.impact.people} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SlaSummary sla={incident.sla} />
        <p className="text-xs text-muted">
          {incident.reportCount} {incident.reportCount === 1 ? 'report' : 'reports'}: {incident.channels.FORM} form, {incident.channels.CHAT} chat, {incident.channels.EMAIL} email
        </p>
      </div>

      {message ? <Banner tone="success" title="Done" role="status">{message}</Banner> : null}
      {error ? <Banner tone="danger" title="Not allowed" role="alert">{error}</Banner> : null}

      <div className="space-y-2">
        <div className="flex flex-wrap gap-2">
          {incident.availableActions.map((action) => <Button key={action.key} variant="secondary" onClick={() => void run(action.key)}>{action.label}</Button>)}
        </div>
        {incident.unavailableActions.map((action) => (
          <p key={action.key} className="text-xs text-muted"><span className="font-medium text-ink">{action.label} is unavailable.</span> {action.reason}</p>
        ))}
      </div>

      <section aria-label="Impact">
        <h3 className="mb-3 text-sm font-semibold text-ink">What this affects</h3>
        <QueryBoundary query={impact}>{(data) => <ImpactChain steps={data.chain as ImpactStep[]} />}</QueryBoundary>
      </section>

      <section aria-label="History">
        <h3 className="mb-3 text-sm font-semibold text-ink">History</h3>
        <Timeline events={incident.timeline.map((event) => ({ id: event.id, title: event.title, detail: event.detail, when: ago(event.at), tone: event.tone }))} />
      </section>
    </div>
  )
}

export function IncidentsScreen({ title, description, variant }: { title: string; description: string; variant: 'department' | 'triage' }) {
  const incidents = useApi<{ items: Incident[] }>('/incidents', { refetchMs: 10_000 })
  const [filter, setFilter] = useState<Filter>('all')
  const [openId, setOpenId] = useState<string | null>(null)

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} actions={<SegmentedControl label="Filter" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'All' }, { value: 'open', label: 'Open' }, { value: 'p1', label: 'P1 only' }]} />} />
      <QueryBoundary query={incidents} isEmpty={(data) => data.items.length === 0} emptyTitle="No incidents">
        {(data) => {
          const rank = { P1: 0, P2: 1, P3: 2, P4: 3 }
          const visible = data.items
            .filter((item) => (filter === 'open' ? !['RESOLVED', 'CLOSED'].includes(item.status) : filter === 'p1' ? item.priority === 'P1' : true))
            .sort((a, b) => rank[a.priority] - rank[b.priority])
          const linked = data.items.filter((item) => item.relatedIds.length > 0)
          const open = data.items.find((item) => item.id === openId)
          return (
            <>
              {variant === 'triage' && linked.length > 1 ? (
                <Banner tone="info" title={`${linked.map((item) => item.id).join(' and ')} share one cause`}>
                  Related reports are kept together, so the Wi-Fi reports and the power fault are handled as one recovery, not 20 separate tickets.
                </Banner>
              ) : null}
              <div className="grid gap-4 sm:grid-cols-4">
                <StatTile label="Open" value={data.items.filter((item) => !['RESOLVED', 'CLOSED'].includes(item.status)).length} tone="accent" />
                <StatTile label="P1" value={data.items.filter((item) => item.priority === 'P1').length} tone="danger" />
                <StatTile label="Reports merged" value={data.items.reduce((sum, item) => sum + Math.max(0, item.reportCount - 1), 0)} hint="Duplicates linked, not lost" />
                <StatTile label="Needs your answer" value={data.items.filter((item) => item.status === 'NEEDS_CLARIFICATION').length} tone="warning" />
              </div>
              <Card>
                {visible.map((incident) => (
                  <ListRow
                    key={incident.id}
                    testId={`incident-${incident.id}`}
                    onClick={() => setOpenId(incident.id)}
                    title={incident.title}
                    subtitle={`${incident.id} · ${incident.buildingName} · ${incident.reportCount} ${incident.reportCount === 1 ? 'report' : 'reports'} · ${ago(incident.updatedAt)}`}
                    trailing={<span className="flex flex-wrap items-center justify-end gap-1.5"><PriorityBadge priority={incident.priority} /><IncidentStatusBadge status={incident.status} /></span>}
                  />
                ))}
              </Card>
              <Sheet open={!!open} title={open ? `${open.id} · ${open.title}` : ''} onClose={() => setOpenId(null)}>
                {open ? <IncidentDetail incident={open} /> : null}
              </Sheet>
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}
