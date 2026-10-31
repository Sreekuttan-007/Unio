import { CheckCircle2, Lock, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Avatar, Badge, Banner, Button, Card, CardBody, CardHeader, DataTable, ListRow, PageHeader, Sheet, StatTile, TextField, Toggle, type Column, type Tone } from '@/ui'
import type { CollisionRule, IntegrationState, ScenarioInfo, SlaPolicy, StockRow, SystemHealth, TechnicianCard, Webhook, WebhookDelivery } from '@/types/domain'
import { describeError } from '../shared/errors'
import { ago, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'
import { SessionCard } from '../shell/SessionCard'
import { InventoryScreen } from '../inventory/InventoryScreen'

export function SystemOverviewScreen() {
  const health = useApi<SystemHealth>('/admin/system/health', { refetchMs: 10_000 })
  return (
    <div className="space-y-5">
      <PageHeader title="System Overview" description="Whether the platform is healthy, and whether the data behind it can be trusted." />
      <QueryBoundary query={health}>
        {(data) => (
          <>
            <div className="grid gap-4 sm:grid-cols-4">
              <StatTile label="API" value={data.api.status === 'UP' ? 'Up' : 'Down'} tone={data.api.status === 'UP' ? 'success' : 'danger'} hint={`${data.api.latencyMs} ms`} />
              <StatTile label="Database" value={data.database.status === 'UP' ? 'Up' : 'Down'} tone={data.database.status === 'UP' ? 'success' : 'danger'} hint={`${data.database.collections} collections, ${data.database.documents} records`} />
              <StatTile label="AI" value={data.ai.status === 'UP' ? 'Up' : data.ai.status === 'OFF' ? 'Off' : 'Degraded'} tone={data.ai.status === 'UP' ? 'success' : 'warning'} hint={data.ai.note} />
              <StatTile label="Background jobs" value={data.jobs.every((job) => job.status === 'OK') ? 'All on time' : 'Late'} tone="success" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader title="Data quality" description="Checks that run on the campus data itself" />
                {data.dataQuality.map((check) => (
                  <ListRow key={check.label} leading={check.ok ? <CheckCircle2 aria-hidden="true" className="size-5 text-success" /> : <XCircle aria-hidden="true" className="size-5 text-warning" />} title={check.label} subtitle={check.detail} trailing={<Badge tone={check.ok ? 'success' : 'warning'}>{check.ok ? 'Passing' : 'Needs attention'}</Badge>} />
                ))}
              </Card>
              <Card>
                <CardHeader title="Scheduled jobs" />
                {data.jobs.map((job) => <ListRow key={job.name} title={job.name} subtitle={`Last ran ${ago(job.lastRun)}`} trailing={<Badge tone={job.status === 'OK' ? 'success' : 'warning'}>{job.status === 'OK' ? 'On time' : 'Late'}</Badge>} />)}
              </Card>
            </div>
          </>
        )}
      </QueryBoundary>
      <SessionCard />
    </div>
  )
}

interface CampusSummary {
  totals: { buildings: number; rooms: number; assets: number }
  buildings: { id: string; code: string; name: string; kind: string; floors: number; rooms: number; assets: number; regionBound: boolean; status: string }[]
}

export function CampusDataScreen() {
  const summary = useApi<CampusSummary>('/admin/campus/summary')
  const columns: Column<CampusSummary['buildings'][number]>[] = [
    { key: 'name', header: 'Building', cell: (row) => (<div><p className="font-medium">{row.name}</p><p className="text-xs text-muted">{row.code} · {titleCase(row.kind)}</p></div>) },
    { key: 'floors', header: 'Floors', className: 'text-right tabular-nums', cell: (row) => row.floors },
    { key: 'rooms', header: 'Rooms', className: 'text-right tabular-nums', cell: (row) => row.rooms },
    { key: 'assets', header: 'Assets', className: 'text-right tabular-nums', cell: (row) => row.assets },
    { key: 'map', header: 'On the map', cell: (row) => <Badge tone={row.regionBound ? 'success' : 'danger'}>{row.regionBound ? 'Bound to a region' : 'Not on the map'}</Badge> },
    { key: 'status', header: 'Status', cell: (row) => <Badge tone={row.status === 'OPEN' ? 'success' : row.status === 'CLOSED' ? 'danger' : 'info'}>{titleCase(row.status)}</Badge> },
  ]
  return (
    <div className="space-y-5">
      <PageHeader title="Campus Master Data" description="The fictional campus every other screen depends on. Each building is bound to a region of the map." />
      <QueryBoundary query={summary}>
        {(data) => (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <StatTile label="Buildings" value={data.totals.buildings} />
              <StatTile label="Rooms" value={data.totals.rooms} />
              <StatTile label="Tracked assets" value={data.totals.assets} hint="Power and network gear carry dependency links" />
            </div>
            <Card><DataTable caption="Buildings" columns={columns} rows={data.buildings} rowKey={(row) => row.id} /></Card>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}

interface Staff {
  technicians: TechnicianCard[]
  faculty: { id: string; name: string; department: string; kind: string }[]
}

export function StaffScreen() {
  const staff = useApi<Staff>('/admin/staff')
  return (
    <div className="space-y-5">
      <PageHeader title="Staff & Skills" description="Who can do what, and when. Assignment checks these before anyone is given work." />
      <QueryBoundary query={staff}>
        {(data) => (
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Technicians" />
              {data.technicians.map((tech) => (
                <ListRow key={tech.id} leading={<Avatar initials={tech.name.split(' ').map((part) => part[0]).join('').slice(0, 2)} size="sm" />} title={tech.name} subtitle={`${tech.department} · ${tech.shift} · ${tech.skills.map((skill) => `${titleCase(skill.code)} L${skill.level}`).join(', ')}`} />
              ))}
            </Card>
            <Card>
              <CardHeader title="Teaching staff" description="Used to find who is affected by a room closure" />
              {data.faculty.map((person) => <ListRow key={person.id} title={person.name} subtitle={`${person.department} · ${titleCase(person.kind)}`} />)}
            </Card>
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}

export function InventoryMasterScreen() {
  return <InventoryScreen title="Inventory Master" description="Items, categories and the levels that trigger a shortage. Stock only moves through receipts and issues." master />
}

export function RulesScreen() {
  const rules = useApi<CollisionRule[]>('/admin/rules')
  const toggle = useAction<{ id: string; enabled: boolean }, CollisionRule>('PATCH', (job) => `/admin/rules/${job.id}`, ['/admin/rules'])
  const [error, setError] = useState<string | null>(null)
  return (
    <div className="space-y-5">
      <PageHeader title="Operational Rules" description="The checks the collision engine runs. Soft rules can be tuned. Rules that protect a safety guarantee are locked." />
      {error ? <Banner tone="danger" title="Not allowed" role="alert">{error}</Banner> : null}
      <QueryBoundary query={rules}>
        {(items) => (
          <Card>
            {items.map((rule) => (
              <div key={rule.id} className="space-y-2 border-b border-line px-5 py-4 last:border-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink">{rule.name}</span>
                  <Badge tone={rule.severity === 'HARD' ? 'danger' : 'warning'}>{rule.severity === 'HARD' ? 'Hard: blocks' : 'Soft: warns'}</Badge>
                  {rule.locked ? <Badge tone="neutral" icon={<Lock aria-hidden="true" className="size-3" />}>Locked</Badge> : null}
                  {rule.parameter ? <Badge tone="info">{rule.parameter}</Badge> : null}
                  <span className="text-xs text-faint">{rule.id}</span>
                </div>
                <Toggle label={rule.enabled ? 'On' : 'Off'} description={rule.description} checked={rule.enabled} onChange={(enabled) => { setError(null); toggle.mutate({ id: rule.id, enabled }, { onError: (failure) => setError(describeError(failure)) }) }} />
              </div>
            ))}
          </Card>
        )}
      </QueryBoundary>
    </div>
  )
}

export function SlaPoliciesScreen() {
  const policies = useApi<SlaPolicy[]>('/admin/sla-policies')
  const columns: Column<SlaPolicy>[] = [
    { key: 'cat', header: 'Category', cell: (row) => titleCase(row.category) },
    { key: 'pri', header: 'Priority', cell: (row) => <Badge tone={row.priority === 'P1' ? 'danger' : row.priority === 'P2' ? 'warning' : 'info'}>{row.priority}</Badge> },
    { key: 'resp', header: 'Respond within', className: 'tabular-nums', cell: (row) => `${row.responseMinutes} min` },
    { key: 'res', header: 'Resolve within', className: 'tabular-nums', cell: (row) => (row.resolutionMinutes >= 60 ? `${row.resolutionMinutes / 60} h` : `${row.resolutionMinutes} min`) },
    { key: 'esc', header: 'Escalation', cell: (row) => row.escalations.map((step) => `${step.atPercent}%: ${step.notify}`).join(' then ') },
  ]
  return (
    <div className="space-y-5">
      <PageHeader title="SLA Policies" description="Targets are data you can change, never numbers buried in code." />
      <QueryBoundary query={policies}>{(items) => <Card><DataTable caption="SLA policies" columns={columns} rows={items} rowKey={(row) => row.id} /></Card>}</QueryBoundary>
    </div>
  )
}

const STATUS_TONE = (status: number): Tone => (status >= 200 && status < 300 ? 'success' : status === 0 ? 'warning' : 'danger')

function DeliveryLog({ hook, onClose }: { hook: Webhook; onClose: () => void }) {
  const deliveries = useApi<WebhookDelivery[]>(`/admin/webhooks/${hook.id}/deliveries`)
  const replay = useAction<{ eventId: string }, { status: number; message: string }>('POST', (job) => `/admin/webhooks/${hook.id}/deliveries/${job.eventId}/replay`, [`/admin/webhooks/${hook.id}/deliveries`])
  const [note, setNote] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">{hook.url}</p>
      {note ? <Banner tone="info" title="Replay" role="status">{note}</Banner> : null}
      <QueryBoundary query={deliveries} isEmpty={(rows) => rows.length === 0} emptyTitle="No deliveries yet" emptyDescription="Nothing has been sent to this webhook.">
        {(rows) => (
          <Card>
            {rows.map((row) => (
              <ListRow
                key={row.eventId}
                title={row.eventType}
                subtitle={`${row.eventId} · ${ago(row.at)}${row.error ? ` · ${row.error}` : ''}`}
                trailing={
                  <div className="flex items-center gap-2">
                    <Badge tone={STATUS_TONE(row.status)}>{row.status || 'No response'}</Badge>
                    <Button
                      variant="secondary"
                      compact
                      loading={replay.isPending}
                      onClick={() => replay.mutate({ eventId: row.eventId }, { onSuccess: (response) => setNote(response.message) })}
                    >
                      Replay
                    </Button>
                  </div>
                }
              />
            ))}
          </Card>
        )}
      </QueryBoundary>
      <Button variant="ghost" onClick={onClose}>Close</Button>
    </div>
  )
}

function AddWebhook() {
  const create = useAction<{ url: string; events: string[] }, Webhook>('POST', '/admin/webhooks', ['/admin/integrations'], { idempotent: true })
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState('workorder.*, approval.*')
  const [error, setError] = useState<string | null>(null)

  const submit = () => {
    setError(null)
    const list = events.split(',').map((item) => item.trim()).filter(Boolean)
    create.mutate({ url: url.trim(), events: list }, { onSuccess: () => { setUrl(''); setEvents('workorder.*, approval.*') }, onError: (failure) => setError(describeError(failure)) })
  }

  return (
    <Card>
      <CardHeader title="Add a webhook" description="A pattern ending in .* matches every event of that kind, and * matches everything." />
      <CardBody className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <TextField label="URL" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/hooks/unio" />
        <TextField label="Events (comma-separated)" value={events} onChange={(event) => setEvents(event.target.value)} />
        <Button loading={create.isPending} disabled={!url.trim() || !events.trim()} onClick={submit}>Add</Button>
        {error ? <p className="sm:col-span-3 text-sm text-danger-ink">{error}</p> : null}
      </CardBody>
    </Card>
  )
}

export function IntegrationsScreen() {
  const state = useApi<IntegrationState>('/admin/integrations')
  const setFeature = useAction<{ key: string; enabled: boolean }, IntegrationState>('PATCH', (job) => `/admin/integrations/features/${job.key}`, ['/admin/integrations'])
  const test = useAction<{ id: string }, { status: number; message: string }>('POST', (job) => `/admin/webhooks/${job.id}/test`, ['/admin/integrations'])
  const toggleHook = useAction<{ id: string; enabled: boolean }, Webhook>('PATCH', (job) => `/admin/webhooks/${job.id}`, ['/admin/integrations'])
  const [result, setResult] = useState<string | null>(null)
  const [openDeliveries, setOpenDeliveries] = useState<Webhook | null>(null)

  return (
    <div className="space-y-5">
      <PageHeader title="AI & Integrations" description="Switch any AI feature off and the workflow keeps running on plain rules. Nothing depends on AI being up." />
      <QueryBoundary query={state}>
        {(data) => (
          <>
            <Card>
              <CardHeader title="AI features" description={`${data.ai.provider}, ${data.ai.model}`} />
              <CardBody className="space-y-1 divide-y divide-line">
                {data.ai.features.map((feature) => (
                  <div key={feature.key} className="flex items-center justify-between gap-3 py-1">
                    <div className="min-w-0 flex-1"><Toggle label={feature.label} checked={feature.enabled} onChange={(enabled) => setFeature.mutate({ key: feature.key, enabled })} /></div>
                    <Badge tone={feature.mode === 'AI' ? 'accent' : 'neutral'}>{feature.mode === 'AI' ? 'AI' : 'Rules'}</Badge>
                  </div>
                ))}
              </CardBody>
            </Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader title="Simulated email inbox" />
                <CardBody className="space-y-1 text-sm">
                  <p><span className="text-muted">Address:</span> {data.email.address}</p>
                  <p><span className="text-muted">Polling:</span> {data.email.polling}</p>
                  <p><span className="text-muted">Last checked:</span> {ago(data.email.lastPoll)}</p>
                  <p><span className="text-muted">Processed:</span> {data.email.processed} messages</p>
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Notification channels" />
                {data.channels.map((channel) => <ListRow key={channel.key} title={channel.label} trailing={<Badge tone={channel.enabled ? 'success' : 'neutral'}>{channel.enabled ? 'On' : 'Off'}</Badge>} />)}
              </Card>
            </div>
            <Card>
              <CardHeader title="Webhooks" description="Signed, and safe to receive twice" />
              {data.webhooks.map((hook) => (
                <ListRow
                  key={hook.id}
                  title={hook.url}
                  subtitle={`${hook.events.join(', ')} · last ${hook.lastStatus || 'never'} ${hook.lastAt ? ago(hook.lastAt) : ''}`}
                  trailing={
                    <div className="flex flex-wrap items-center gap-2">
                      <Toggle label="On" checked={hook.enabled} onChange={(enabled) => toggleHook.mutate({ id: hook.id, enabled })} />
                      <Button variant="secondary" compact onClick={() => setOpenDeliveries(hook)}>Deliveries</Button>
                      <Button variant="secondary" compact loading={test.isPending} onClick={() => test.mutate({ id: hook.id }, { onSuccess: (response) => setResult(response.message) })}>Send test</Button>
                    </div>
                  }
                />
              ))}
            </Card>
            {result ? <Banner tone="success" title="Webhook test" role="status">{result}</Banner> : null}
            <AddWebhook />
            <Sheet open={!!openDeliveries} title={openDeliveries ? `Deliveries · ${openDeliveries.id}` : ''} onClose={() => setOpenDeliveries(null)}>
              {openDeliveries ? <DeliveryLog hook={openDeliveries} onClose={() => setOpenDeliveries(null)} /> : null}
            </Sheet>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}

export function SeedScreen() {
  const scenarios = useApi<ScenarioInfo[]>('/admin/scenarios')
  const reset = useAction<{ id: string }, { message: string }>('POST', (job) => `/admin/scenarios/${job.id}/reset`, ['/'])
  const [message, setMessage] = useState<string | null>(null)
  const stocks = useApi<StockRow[]>('/inventory/items', { enabled: false })
  void stocks
  return (
    <div className="space-y-5">
      <PageHeader title="Seed & Demo Data" description="Put the campus into a known scenario in one click, with all times moved to now. This is for demos and testing only." />
      {message ? <Banner tone="success" title="Reset" role="status">{message}</Banner> : null}
      <QueryBoundary query={scenarios}>
        {(items) => (
          <ul className="grid gap-4 md:grid-cols-2">
            {items.map((scenario) => (
              <li key={scenario.id}>
                <Card className="h-full" data-testid={`scenario-${scenario.id}`}>
                  <CardBody className="flex h-full flex-col gap-3">
                    <h2 className="text-base font-semibold text-ink">{scenario.title}</h2>
                    <p className="text-sm text-muted">{scenario.description}</p>
                    <div className="flex flex-wrap gap-1.5">{scenario.covers.map((item) => <Badge key={item} tone={('accent' as Tone)}>{item}</Badge>)}</div>
                    <Button className="mt-auto self-start" variant="secondary" loading={reset.isPending} onClick={() => reset.mutate({ id: scenario.id }, { onSuccess: (response) => setMessage(response.message) })}>Reset to scenario {scenario.id}</Button>
                  </CardBody>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
    </div>
  )
}
