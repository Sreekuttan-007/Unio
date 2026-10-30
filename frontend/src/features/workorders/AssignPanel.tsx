import { useState } from 'react'
import { Badge, Banner, Button, Card, CardBody, Checkbox, TextArea } from '@/ui'
import type { Candidate, Finding, WorkOrder } from '@/types/domain'
import { ApiError } from '@/platform/api/client'
import { describeError } from '../shared/errors'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

const DECISION = { ALLOW: 'success', WARN: 'warning', BLOCK: 'danger' } as const
const DECISION_LABEL = { ALLOW: 'Allowed', WARN: 'Warning', BLOCK: 'Blocked' } as const

/**
 * Ranked technicians for a work order, each with the collision engine verdict. A blocked
 * choice is refused by the server and the reason is shown. A warning needs a reason.
 */
export function AssignPanel({ order, onAssigned }: { order: WorkOrder; onAssigned?: () => void }) {
  const candidates = useApi<Candidate[]>(`/work-orders/${order.id}/candidates`)
  const assign = useAction<{ technicianId: string; acknowledged?: boolean; overrideReason?: string }, WorkOrder>('POST', `/work-orders/${order.id}/assign`, ['/work-orders', '/technicians'])
  const [pending, setPending] = useState<Candidate | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [reason, setReason] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const attempt = async (candidate: Candidate, withReason = false) => {
    setError(null)
    setPending(candidate)
    try {
      await assign.mutateAsync({ technicianId: candidate.technicianId, acknowledged: withReason ? acknowledged : undefined, overrideReason: withReason ? reason : undefined })
      setDone(`${order.id} is now assigned to ${candidate.name}.`)
      setPending(null)
      onAssigned?.()
    } catch (failure) {
      if (failure instanceof ApiError && failure.code === 'COLLISION_WARNING') {
        setFindings((failure.details.findings as Finding[]) ?? [])
      } else {
        setFindings(failure instanceof ApiError ? ((failure.details.findings as Finding[]) ?? []) : [])
        setError(describeError(failure))
        setPending(null)
      }
    }
  }

  return (
    <section aria-label="Assign a technician" className="space-y-3">
      <h3 className="text-sm font-semibold text-ink">{order.needsReassignment ? 'Choose a replacement' : 'Assign a technician'}</h3>
      {done ? <Banner tone="success" title="Assigned" role="status">{done}</Banner> : null}
      {error ? <Banner tone="danger" title="The collision engine refused this" role="alert">{error}</Banner> : null}
      <QueryBoundary query={candidates}>
        {(items) => (
          <ul className="space-y-2">
            {items.map((candidate) => (
              <li key={candidate.technicianId}>
                <Card data-testid={`candidate-${candidate.technicianId}`}>
                  <CardBody className="space-y-2 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-ink">{candidate.name}</span>
                        <Badge tone={DECISION[candidate.decision]}>{DECISION_LABEL[candidate.decision]}</Badge>
                      </div>
                      <Button variant={candidate.decision === 'BLOCK' ? 'ghost' : 'secondary'} compact loading={assign.isPending && pending?.technicianId === candidate.technicianId} onClick={() => void attempt(candidate)}>
                        Assign
                      </Button>
                    </div>
                    <p className="text-xs text-muted">{candidate.factors.map((factor) => `${factor.label}: ${factor.value}`).join(' · ')}</p>
                    {candidate.findings.map((finding) => (
                      <p key={finding.code} className={finding.severity === 'HARD' ? 'text-sm text-danger-ink' : 'text-sm text-warning-ink'}>
                        <span className="font-medium">{finding.severity === 'HARD' ? 'Blocks: ' : 'Warns: '}</span>{finding.message}
                      </p>
                    ))}
                    {pending?.technicianId === candidate.technicianId && findings.some((finding) => finding.severity === 'SOFT') && !assign.isSuccess ? (
                      <div className="space-y-2 rounded-md bg-warning-soft p-3">
                        <p className="text-sm font-medium text-warning-ink">A warning needs a reason. It is recorded in the audit trail.</p>
                        <TextArea label="Reason" value={reason} onChange={(event) => setReason(event.target.value)} />
                        <Checkbox label="I accept this warning" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
                        <Button disabled={!acknowledged || reason.trim().length < 5} onClick={() => void attempt(candidate, true)}>Assign anyway</Button>
                      </div>
                    ) : null}
                  </CardBody>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </QueryBoundary>
    </section>
  )
}
