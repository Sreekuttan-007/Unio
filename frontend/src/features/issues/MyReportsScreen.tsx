import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, ListRow, PageHeader, Sheet, Timeline } from '@/ui'
import type { ReportSummary } from '@/types/domain'
import { IncidentStatusBadge, PriorityBadge } from '../shared/badges'
import { ago, titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'
import { useNavTo } from '../shared/useNavTo'

export function MyReportsScreen() {
  const reports = useApi<ReportSummary[]>('/issues/mine', { refetchMs: 15_000 })
  const [openId, setOpenId] = useState<string | null>(null)
  const [thanks, setThanks] = useState(false)
  const feedback = useAction<{ id: string; fixed: boolean }>('POST', (body) => `/issues/${body.id}/feedback`, ['/issues/mine'])
  const { go } = useNavTo()

  return (
    <div>
      <PageHeader title="My Reports" description="Everything you reported, from submission to closure." actions={<Button onClick={() => go('student.report')}>Report an issue</Button>} />
      <QueryBoundary query={reports} isEmpty={(items) => items.length === 0} emptyTitle="You have not reported anything" emptyDescription="When you report a problem it shows up here with live updates.">
        {(items) => {
          const open = items.find((item) => item.id === openId)
          return (
            <>
              <Card>
                {items.map((item) => (
                  <ListRow
                    key={item.id}
                    testId={`report-${item.id}`}
                    onClick={() => { setOpenId(item.id); setThanks(false) }}
                    title={item.title}
                    subtitle={`${item.id} · ${item.incidentId} · ${titleCase(item.channel)} · ${ago(item.submittedAt)}`}
                    trailing={<IncidentStatusBadge status={item.status} />}
                  />
                ))}
              </Card>
              <Sheet open={!!open} title={open?.title ?? ''} onClose={() => setOpenId(null)}>
                {open ? (
                  <div className="space-y-5">
                    <div className="flex flex-wrap gap-2">
                      <IncidentStatusBadge status={open.status} />
                      <PriorityBadge priority={open.priority} />
                      {open.incidentReportCount > 1 ? <Badge tone="info">{open.incidentReportCount} people reported this</Badge> : null}
                    </div>
                    <p className="text-sm text-ink">{open.summary}</p>
                    <Timeline events={open.timeline.map((event) => ({ id: event.id, title: event.title, detail: event.detail, when: ago(event.at), tone: event.tone }))} />
                    {open.canGiveFeedback && !thanks ? (
                      <Card>
                        <CardBody className="space-y-3">
                          <p className="text-sm font-medium text-ink">Is this fixed?</p>
                          <div className="flex gap-2">
                            <Button variant="secondary" onClick={() => feedback.mutate({ id: open.id, fixed: true }, { onSuccess: () => setThanks(true) })}>Yes, fixed</Button>
                            <Button variant="ghost" onClick={() => feedback.mutate({ id: open.id, fixed: false }, { onSuccess: () => setThanks(true) })}>Not fixed</Button>
                          </div>
                        </CardBody>
                      </Card>
                    ) : null}
                    {thanks ? <Banner tone="success" title="Thank you" role="status">Your answer helps us close this properly.</Banner> : null}
                  </div>
                ) : null}
              </Sheet>
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}
