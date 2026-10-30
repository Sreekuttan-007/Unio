import { Mail, Send } from 'lucide-react'
import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, CardHeader, ListRow, PageHeader, TextArea, TextField, type Tone } from '@/ui'
import type { InboundEmail } from '@/types/domain'
import { ago, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

const STATUS: Record<InboundEmail['status'], { tone: Tone; label: string }> = {
  PENDING: { tone: 'warning', label: 'Waiting' },
  CONVERTED: { tone: 'success', label: 'Became a report' },
  CLARIFICATION_SENT: { tone: 'info', label: 'Question sent' },
  DUPLICATE_IGNORED: { tone: 'neutral', label: 'Duplicate, ignored' },
}

export function InboxScreen() {
  const emails = useApi<InboundEmail[]>('/inbox', { refetchMs: 8_000 })
  const [openId, setOpenId] = useState<string | null>('EML-7018')
  const [draft, setDraft] = useState({ from: 'student@students.aurora.example', subject: 'Fan not working in BHB-102', text: 'The ceiling fan in BHB-102 has stopped working.' })
  const process = useAction<{ id: string }, InboundEmail>('POST', (job) => `/inbox/${job.id}/process`, ['/inbox', '/incidents'])
  const simulate = useAction<typeof draft, InboundEmail>('POST', '/inbox/simulate', ['/inbox'])

  return (
    <div className="space-y-5">
      <PageHeader title="Intake Inbox" description="A simulated mailbox. Each message is read, matched to existing incidents, and turned into a report, or answered with a question." />
      <QueryBoundary query={emails} isEmpty={(items) => items.length === 0} emptyTitle="The inbox is empty">
        {(items) => {
          const open = items.find((item) => item.id === openId) ?? items[0]
          return (
            <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
              <Card>
                {items.map((email) => (
                  <ListRow
                    key={email.id}
                    testId={`email-${email.id}`}
                    selected={email.id === open?.id}
                    onClick={() => setOpenId(email.id)}
                    leading={<Mail aria-hidden="true" className="size-5 shrink-0 text-muted" />}
                    title={email.subject}
                    subtitle={`${email.from} · ${ago(email.receivedAt)}`}
                    trailing={<Badge tone={STATUS[email.status].tone}>{STATUS[email.status].label}</Badge>}
                  />
                ))}
              </Card>
              {open ? (
                <Card>
                  <CardHeader title={open.subject} description={`${open.from} · ${ago(open.receivedAt)}`} action={<Badge tone={STATUS[open.status].tone}>{STATUS[open.status].label}</Badge>} />
                  <CardBody className="space-y-4">
                    <p className="whitespace-pre-wrap rounded-md bg-surface-2 p-3 text-sm text-ink">{open.body}</p>
                    {open.extraction ? (
                      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                        <div><dt className="text-xs text-muted">Type</dt><dd className="font-medium">{titleCase(open.extraction.category)}</dd></div>
                        <div><dt className="text-xs text-muted">Where</dt><dd className="font-medium">{open.extraction.location}</dd></div>
                        <div><dt className="text-xs text-muted">Urgency</dt><dd className="font-medium">{titleCase(open.extraction.urgency)}</dd></div>
                        <div><dt className="text-xs text-muted">Sure</dt><dd className="font-medium">{Math.round(open.extraction.confidence * 100)}%</dd></div>
                      </dl>
                    ) : null}
                    {open.note ? <Banner tone={open.note.includes('ignored') ? 'warning' : 'info'} title="What the system did">{open.note}</Banner> : null}
                    {open.incidentId ? <p className="text-sm text-muted">Incident <span className="font-medium text-ink">{open.incidentId}</span></p> : null}
                    {open.status === 'PENDING' ? <Button loading={process.isPending} onClick={() => process.mutate({ id: open.id })}>Turn into a report</Button> : null}
                  </CardBody>
                </Card>
              ) : null}
            </div>
          )
        }}
      </QueryBoundary>
      <Card>
        <CardHeader title="Send a test email" description="Simulates a message arriving in the mailbox. Sending the same one twice creates one report." />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <TextField label="From" value={draft.from} onChange={(event) => setDraft({ ...draft, from: event.target.value })} />
          <TextField label="Subject" value={draft.subject} onChange={(event) => setDraft({ ...draft, subject: event.target.value })} />
          <div className="sm:col-span-2"><TextArea label="Message" value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} /></div>
          <div className="sm:col-span-2"><Button icon={<Send aria-hidden="true" className="size-4" />} loading={simulate.isPending} onClick={() => simulate.mutate(draft, { onSuccess: (email) => setOpenId(email.id) })}>Send test email</Button></div>
        </CardBody>
      </Card>
    </div>
  )
}
