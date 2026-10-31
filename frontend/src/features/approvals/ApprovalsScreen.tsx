import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, CardHeader, ListRow, PageHeader, SegmentedControl, SelectField, Sheet, StatTile, TextArea, TextField, Timeline } from '@/ui'
import type { Approval } from '@/types/domain'
import { useAuth } from '@/platform/auth/AuthProvider'
import { ApprovalStatusBadge } from '../shared/badges'
import { describeError } from '../shared/errors'
import { ago, money, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

const TYPE_LABEL: Record<Approval['type'], string> = { PURCHASE: 'Purchase', COSTLY_REPAIR: 'Costly repair', OVERRIDE: 'Override' }
const EVIDENCE_TONE = { neutral: 'text-ink', warning: 'text-warning-ink', danger: 'text-danger-ink', success: 'text-success-ink' } as const
const OPEN = ['SUBMITTED', 'UNDER_REVIEW', 'NEEDS_CLARIFICATION']

function ClarificationAnswer({ approval, onDone }: { approval: Approval; onDone: () => void }) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const answer = useAction<{ id: string; text: string }, Approval>('POST', (job) => `/approvals/${job.id}/answer`, ['/approvals'])
  const question = [...approval.decisions].reverse().find((item) => item.decision === 'CLARIFICATION REQUESTED')?.reason

  const send = async () => {
    setError(null)
    try {
      await answer.mutateAsync({ id: approval.id, text })
      onDone()
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  return (
    <div className="space-y-3">
      <Banner tone="warning" title="They asked a question">{question ?? 'Someone asked a question about this request.'}</Banner>
      {error ? <Banner tone="danger" title="Refused" role="alert"><span data-testid="approval-error">{error}</span></Banner> : null}
      <TextArea label="Your answer" value={text} onChange={(event) => setText(event.target.value)} />
      <Button loading={answer.isPending} disabled={!text.trim()} onClick={() => void send()}>Send answer</Button>
    </div>
  )
}

function Detail({ approval, onDone }: { approval: Approval; onDone: () => void }) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const decide = useAction<{ id: string; decision: 'APPROVE' | 'REJECT' | 'CLARIFY'; reason: string }, Approval>('POST', (job) => `/approvals/${job.id}/decide`, ['/approvals'])
  // The server never offers an "answer" action key: the requester always gets an empty
  // availableActions plus this one specific unavailable "approve" hint. That combination is
  // what distinguishes "this is my own request" from "I simply can't decide this one."
  const awaitingMyAnswer = approval.status === 'NEEDS_CLARIFICATION' && approval.availableActions.length === 0 && approval.unavailableActions.some((action) => action.key === 'approval.approve')

  const act = async (decision: 'APPROVE' | 'REJECT' | 'CLARIFY') => {
    setError(null)
    try {
      await decide.mutateAsync({ id: approval.id, decision, reason })
      onDone()
    } catch (failure) {
      setError(describeError(failure))
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <ApprovalStatusBadge status={approval.status} />
        <Badge tone="accent">{TYPE_LABEL[approval.type]}</Badge>
        {approval.amountPaise > 0 ? <Badge>{money(approval.amountPaise)}</Badge> : null}
        {approval.linkedWorkOrderId ? <Badge tone="info">Work order {approval.linkedWorkOrderId}</Badge> : null}
        {approval.linkedIncidentId ? <Badge tone="info">Incident {approval.linkedIncidentId}</Badge> : null}
      </div>
      <p className="text-sm text-ink">{approval.justification}</p>
      <p className="text-xs text-muted">Raised by {approval.requesterName} · {ago(approval.createdAt)}</p>

      {approval.lines.length > 0 ? (
        <Card>
          <CardBody className="p-0">
            {approval.lines.map((line) => <ListRow key={line.name} title={line.name} subtitle={`Quantity ${line.qty}`} meta={money(line.estimatePaise * line.qty)} />)}
          </CardBody>
        </Card>
      ) : null}

      {approval.evidence.length > 0 ? (
        <section aria-label="Evidence">
          <h3 className="mb-2 text-sm font-semibold text-ink">What the system checked</h3>
          <dl className="space-y-2 text-sm">
            {approval.evidence.map((item) => (
              <div key={item.label} className="flex justify-between gap-4 border-b border-line pb-2 last:border-0">
                <dt className="text-muted">{item.label}</dt>
                <dd className={`text-right font-medium ${EVIDENCE_TONE[item.tone ?? 'neutral']}`}>{item.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      <Banner tone="info" title="Routing">{approval.routing}</Banner>

      {approval.decisions.length > 0 ? <Timeline events={approval.decisions.map((item, index) => ({ id: String(index), title: `${item.decision} by ${item.by}`, detail: item.reason ?? undefined, when: ago(item.at), tone: item.decision.startsWith('APPROVED') ? 'success' : 'warning' }))} /> : null}

      {error ? <Banner tone="danger" title="Refused" role="alert"><span data-testid="approval-error">{error}</span></Banner> : null}

      {awaitingMyAnswer ? <ClarificationAnswer approval={approval} onDone={onDone} /> : null}

      {!awaitingMyAnswer && approval.availableActions.length > 0 ? (
        <div className="space-y-3">
          <TextArea label="Reason (kept in the audit trail)" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="flex flex-wrap gap-2">
            {approval.availableActions.map((action) => {
              const decision = action.key === 'approval.approve' ? 'APPROVE' : action.key === 'approval.reject' ? 'REJECT' : 'CLARIFY'
              return <Button key={action.key} variant={decision === 'APPROVE' ? 'primary' : decision === 'REJECT' ? 'danger' : 'secondary'} loading={decide.isPending} onClick={() => void act(decision)}>{action.label}</Button>
            })}
          </div>
        </div>
      ) : null}
      {!awaitingMyAnswer && approval.unavailableActions.map((action) => (
        <div key={action.key} className="space-y-2">
          <Button disabled>{action.label}</Button>
          <p className="text-sm text-muted" data-testid="approval-blocked">{action.reason}</p>
          {/* The server also refuses the call, so this is a courtesy, not the control. */}
          <Button variant="ghost" compact onClick={() => void act('APPROVE')}>Try anyway</Button>
        </div>
      ))}
    </div>
  )
}

function RaiseRequest() {
  const [form, setForm] = useState({ type: 'PURCHASE' as Approval['type'], title: '', justification: '', amount: 2900 })
  const [message, setMessage] = useState<string | null>(null)
  const create = useAction<{ type: Approval['type']; title: string; justification: string; amountPaise: number }, Approval>('POST', '/approvals', ['/approvals'], { idempotent: true })
  return (
    <Card>
      <CardHeader title="Raise a request" description="Purchases, costly repairs and overrides all go through the same approval, with the amount deciding who sees it." />
      <CardBody className="grid gap-4 sm:grid-cols-2">
        <SelectField label="Type" value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value as Approval['type'] })} options={Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))} />
        <TextField label="Amount in rupees" type="number" min={0} value={form.amount} onChange={(event) => setForm({ ...form, amount: Number(event.target.value) })} />
        <div className="sm:col-span-2"><TextField label="What do you need" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></div>
        <div className="sm:col-span-2"><TextArea label="Why" value={form.justification} onChange={(event) => setForm({ ...form, justification: event.target.value })} /></div>
        <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
          <Button loading={create.isPending} disabled={!form.title || !form.justification} onClick={() => create.mutate({ type: form.type, title: form.title, justification: form.justification, amountPaise: form.amount * 100 }, { onSuccess: (item) => { setMessage(`${item.id} was sent. ${item.routing}`); setForm({ ...form, title: '', justification: '' }) } })}>Send request</Button>
          {message ? <span role="status" className="text-sm text-success-ink">{message}</span> : null}
        </div>
      </CardBody>
    </Card>
  )
}

export function ApprovalsScreen({ title, description, mode }: { title: string; description: string; mode: 'queue' | 'all' | 'mine' }) {
  const approvals = useApi<{ items: Approval[] }>('/approvals', { refetchMs: 10_000 })
  const { bootstrap } = useAuth()
  const [filter, setFilter] = useState<'open' | 'all'>(mode === 'queue' ? 'open' : 'all')
  const [openId, setOpenId] = useState<string | null>(null)
  const canRaise = !!bootstrap?.permissions.includes('approval.request.create')

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} actions={mode !== 'queue' ? <SegmentedControl label="Show" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'Everything' }, { value: 'open', label: 'Waiting' }]} /> : undefined} />
      <QueryBoundary query={approvals} isEmpty={(data) => data.items.length === 0} emptyTitle="Nothing waiting" emptyDescription="Requests appear here as they are raised.">
        {(data) => {
          const visible = data.items.filter((item) => (filter === 'open' ? OPEN.includes(item.status) : true))
          const pending = data.items.filter((item) => OPEN.includes(item.status))
          const open = data.items.find((item) => item.id === openId)
          return (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <StatTile label="Waiting" value={pending.length} tone="warning" />
                <StatTile label="Value waiting" value={money(pending.reduce((sum, item) => sum + item.amountPaise, 0))} />
                <StatTile label="Decided" value={data.items.length - pending.length} tone="success" />
              </div>
              <Card>
                {visible.map((approval) => (
                  <ListRow
                    key={approval.id}
                    testId={`approval-${approval.id}`}
                    onClick={() => setOpenId(approval.id)}
                    title={approval.title}
                    subtitle={`${approval.id} · ${TYPE_LABEL[approval.type]} · ${approval.requesterName} · ${ago(approval.createdAt)}`}
                    meta={approval.amountPaise > 0 ? money(approval.amountPaise) : undefined}
                    trailing={<ApprovalStatusBadge status={approval.status} />}
                  />
                ))}
              </Card>
              <Sheet open={!!open} title={open ? `${open.id} · ${open.title}` : ''} onClose={() => setOpenId(null)}>
                {open ? <Detail approval={open} onDone={() => setOpenId(null)} /> : null}
              </Sheet>
            </>
          )
        }}
      </QueryBoundary>
      {canRaise && mode !== 'queue' ? <RaiseRequest /> : null}
      <p className="text-xs text-muted">{titleCase('Nobody can approve a request they raised, and the server enforces that.')}</p>
    </div>
  )
}
