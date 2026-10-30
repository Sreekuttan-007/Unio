import { useState } from 'react'
import { Check, ShieldAlert, X } from 'lucide-react'
import { Badge, Banner, Button, Card, CardBody, ListRow, PageHeader, PlanCard, SegmentedControl, StatTile, type Tone } from '@/ui'
import type { CollisionRecord, Incident, SimulationRun } from '@/types/domain'
import { describeError } from '../shared/errors'
import { ago, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

const DECISION: Record<CollisionRecord['decision'], { tone: Tone; label: string }> = {
  ALLOW: { tone: 'success', label: 'Allowed' },
  WARN: { tone: 'warning', label: 'Warning' },
  REQUIRE_APPROVAL: { tone: 'info', label: 'Needs approval' },
  BLOCK: { tone: 'danger', label: 'Blocked' },
}

export function CollisionReviewScreen() {
  const records = useApi<CollisionRecord[]>('/collisions', { refetchMs: 10_000 })
  const [filter, setFilter] = useState<'all' | 'BLOCK' | 'WARN'>('all')
  return (
    <div className="space-y-5">
      <PageHeader title="Collision Review" description="Every check the engine ran, why it decided that way, and every override with its reason." />
      <QueryBoundary query={records} isEmpty={(items) => items.length === 0} emptyTitle="No checks yet">
        {(items) => {
          const visible = items.filter((item) => filter === 'all' || item.decision === filter)
          return (
            <>
              <div className="grid gap-4 sm:grid-cols-4">
                <StatTile label="Checks today" value={items.length} />
                <StatTile label="Blocked" value={items.filter((item) => item.decision === 'BLOCK').length} tone="danger" hint="Never overridable" />
                <StatTile label="Warnings" value={items.filter((item) => item.decision === 'WARN').length} tone="warning" />
                <StatTile label="Overrides" value={items.filter((item) => item.override).length} tone="info" hint="Each has a reason" />
              </div>
              <SegmentedControl label="Show" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'Everything' }, { value: 'BLOCK', label: 'Blocked' }, { value: 'WARN', label: 'Warnings' }]} />
              <ul className="space-y-3">
                {visible.map((record) => (
                  <li key={record.id}>
                    <Card data-testid={`collision-${record.id}`}>
                      <CardBody className="space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-ink">{record.summary}</p>
                            <p className="text-xs text-muted">{titleCase(record.actionType)} · {record.actor} · {ago(record.at)} · {record.id}</p>
                          </div>
                          <Badge tone={DECISION[record.decision].tone} icon={record.decision === 'ALLOW' ? <Check aria-hidden="true" className="size-3" /> : record.decision === 'BLOCK' ? <X aria-hidden="true" className="size-3" /> : <ShieldAlert aria-hidden="true" className="size-3" />}>
                            {DECISION[record.decision].label}
                          </Badge>
                        </div>
                        {record.findings.map((finding) => (
                          <p key={finding.code} className={`rounded-md px-3 py-2 text-sm ${finding.severity === 'HARD' ? 'bg-danger-soft text-danger-ink' : 'bg-warning-soft text-warning-ink'}`}>
                            <span className="font-semibold">{finding.severity === 'HARD' ? 'Hard rule, cannot be overridden. ' : 'Soft rule. '}</span>{finding.message}
                          </p>
                        ))}
                        {record.findings.length === 0 ? <p className="text-sm text-muted">No conflicts found.</p> : null}
                        {record.override ? <p className="text-sm text-ink"><span className="font-medium">Override by {record.override.by}:</span> “{record.override.reason}”</p> : null}
                      </CardBody>
                    </Card>
                  </li>
                ))}
              </ul>
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}

interface ExecuteResult {
  status: 'EXECUTED' | 'STALE'
  message: string
}

export function SimulatorScreen() {
  const incidents = useApi<{ items: Incident[] }>('/incidents')
  const [picked, setPicked] = useState('')
  const [run, setRun] = useState<SimulationRun | null>(null)
  const [result, setResult] = useState<ExecuteResult | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const simulate = useAction<{ incidentId: string }, SimulationRun>('POST', '/simulations')
  const execute = useAction<{ runId: string; planId: string }, ExecuteResult>('POST', (job) => `/simulations/${job.runId}/plans/${job.planId}/execute`, ['/incidents', '/timetable'])

  const start = async () => {
    setError(null)
    setResult(null)
    setConfirming(null)
    try {
      setRun(await simulate.mutateAsync({ incidentId }))
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const apply = async (planId: string) => {
    if (!run) return
    try {
      setResult(await execute.mutateAsync({ runId: run.id, planId }))
      setConfirming(null)
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  const open = (incidents.data?.items ?? []).filter((item) => ['P1', 'P2'].includes(item.priority) && !['RESOLVED', 'CLOSED'].includes(item.status))
  const incidentId = picked || open[0]?.id || ''

  return (
    <div className="space-y-5">
      <PageHeader title="What-If Simulator" description="Compare recovery plans against a frozen copy of the campus. Nothing here changes live data until you execute a plan, and it is checked again first." />
      <Card>
        <CardBody className="flex flex-wrap items-end gap-3">
          <label className="min-w-64 flex-1 space-y-1.5 text-sm font-medium text-ink">
            Incident to recover from
            <select value={incidentId} onChange={(event) => setPicked(event.target.value)} className="mt-1.5 min-h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-sm">
              {open.map((incident) => <option key={incident.id} value={incident.id}>{incident.id} · {incident.title}</option>)}
              {open.length === 0 ? <option value="">No urgent incident is open</option> : null}
            </select>
          </label>
          <Button loading={simulate.isPending} disabled={!incidentId} onClick={() => void start()}>Run simulation</Button>
        </CardBody>
      </Card>
      {error ? <Banner tone="danger" title="That did not work" role="alert">{error}</Banner> : null}
      {result ? <Banner tone={result.status === 'EXECUTED' ? 'success' : 'warning'} title={result.status === 'EXECUTED' ? 'Plan executed' : 'Plan is stale'} role="status">{result.message}</Banner> : null}
      {run ? (
        <>
          <Banner tone="info" title="Read-only snapshot">Taken {ago(run.snapshotAt)}. Running this simulation did not write to any live record.</Banner>
          <div className="grid gap-4 xl:grid-cols-3">
            {run.plans.map((plan) => (
              <PlanCard
                key={plan.id}
                title={`Plan ${plan.id}: ${plan.title}`}
                summary={plan.summary}
                feasible={plan.feasible}
                recommended={plan.id === run.recommendedPlanId}
                metrics={plan.metrics}
                findings={plan.findings}
                action={
                  plan.feasible ? (
                    confirming === plan.id ? (
                      <div className="space-y-2">
                        <p className="text-xs text-muted">This will check the plan against live data once more, then apply: {plan.actions.join('; ')}.</p>
                        <div className="flex gap-2">
                          <Button loading={execute.isPending} onClick={() => void apply(plan.id)}>Confirm and execute</Button>
                          <Button variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button>
                        </div>
                      </div>
                    ) : (
                      <Button variant="secondary" onClick={() => setConfirming(plan.id)}>Execute this plan</Button>
                    )
                  ) : (
                    <p className="text-xs text-muted">A blocked plan cannot be executed.</p>
                  )
                }
              />
            ))}
          </div>
        </>
      ) : (
        <ListRow title="No simulation yet" subtitle="Pick an incident and run one to compare recovery options." />
      )}
    </div>
  )
}
