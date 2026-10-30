import { useState } from 'react'
import { Avatar, Badge, Banner, Button, Card, CardBody, PageHeader, ProgressBar, type Tone } from '@/ui'
import type { TechnicianCard, WorkOrder } from '@/types/domain'
import { titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'
import { WorkOrderSheet } from './WorkOrderSheet'

const AVAILABILITY: Record<TechnicianCard['availability'], { tone: Tone; label: string }> = {
  AVAILABLE: { tone: 'success', label: 'Available' },
  BUSY: { tone: 'info', label: 'Busy' },
  ON_LEAVE: { tone: 'neutral', label: 'On leave' },
  SICK: { tone: 'danger', label: 'Off sick' },
  OFF_SHIFT: { tone: 'neutral', label: 'Off shift' },
}

const initials = (name: string) => name.split(' ').map((part) => part[0]).join('').slice(0, 2)

export function TechniciansScreen() {
  const technicians = useApi<TechnicianCard[]>('/technicians', { refetchMs: 10_000 })
  const orders = useApi<{ items: WorkOrder[] }>('/work-orders', { refetchMs: 10_000 })
  const [openId, setOpenId] = useState<string | null>(null)
  const flagged = (orders.data?.items ?? []).filter((order) => order.needsReassignment)

  return (
    <div className="space-y-5">
      <PageHeader title="Technicians" description="Skills, shifts, availability and workload. Assignment is checked against all of them." />
      {flagged.map((order) => (
        <Banner key={order.id} tone="warning" title={`${order.id} needs a new technician`} action={<Button variant="secondary" compact onClick={() => setOpenId(order.id)}>Reassign</Button>}>
          {order.needsReassignment?.reason}. {order.needsReassignment?.suggestedName} is the best qualified replacement.
        </Banner>
      ))}
      <QueryBoundary query={technicians}>
        {(items) => (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((tech) => {
              const status = AVAILABILITY[tech.availability]
              return (
                <li key={tech.id}>
                  <Card className="h-full" data-testid={`tech-${tech.id}`}>
                    <CardBody className="space-y-3">
                      <div className="flex items-start gap-3">
                        <Avatar initials={initials(tech.name)} size="lg" />
                        <div className="min-w-0 flex-1">
                          <p className="font-semibold text-ink">{tech.name}</p>
                          <p className="text-xs text-muted">{tech.department} · {tech.shift}</p>
                        </div>
                        <Badge tone={status.tone}>{status.label}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {tech.skills.map((skill) => <Badge key={skill.code} tone="accent">{titleCase(skill.code)} L{skill.level}</Badge>)}
                      </div>
                      <ProgressBar label={`Workload, ${tech.openTasks} of ${tech.maxTasks} tasks`} value={tech.workloadPercent} tone={tech.workloadPercent > 80 ? 'danger' : tech.workloadPercent > 60 ? 'warning' : 'success'} />
                      <p className="text-xs text-muted">{tech.currentTask ?? 'Nothing assigned'}</p>
                    </CardBody>
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </QueryBoundary>
      <WorkOrderSheet order={orders.data?.items.find((order) => order.id === openId)} onClose={() => setOpenId(null)} canAssign />
    </div>
  )
}
