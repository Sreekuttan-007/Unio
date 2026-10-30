import { Badge, SlaMeter, slaTone, type Tone } from '@/ui'
import type { Approval, Category, IncidentStatus, Priority, Sla, WorkOrderStatus } from '@/types/domain'
import { titleCase } from './format'

const PRIORITY: Record<Priority, { tone: Tone; label: string }> = {
  P1: { tone: 'danger', label: 'P1 Critical' },
  P2: { tone: 'warning', label: 'P2 High' },
  P3: { tone: 'info', label: 'P3 Medium' },
  P4: { tone: 'neutral', label: 'P4 Low' },
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge tone={PRIORITY[priority].tone}>{PRIORITY[priority].label}</Badge>
}

const INCIDENT: Record<IncidentStatus, Tone> = {
  SUBMITTED: 'neutral',
  UNDER_REVIEW: 'neutral',
  NEEDS_CLARIFICATION: 'warning',
  ACKNOWLEDGED: 'info',
  ASSIGNED: 'accent',
  IN_PROGRESS: 'accent',
  RESOLVED: 'success',
  CLOSED: 'neutral',
}

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return <Badge tone={INCIDENT[status]}>{titleCase(status)}</Badge>
}

const WORK_ORDER: Record<WorkOrderStatus, Tone> = {
  PENDING_ASSIGNMENT: 'warning',
  ASSIGNED: 'info',
  ACCEPTED: 'info',
  IN_PROGRESS: 'accent',
  BLOCKED: 'danger',
  COMPLETED: 'success',
  VERIFIED: 'success',
  CLOSED: 'neutral',
  CANCELLED: 'neutral',
}

export function WorkOrderStatusBadge({ status }: { status: WorkOrderStatus }) {
  return <Badge tone={WORK_ORDER[status]}>{titleCase(status)}</Badge>
}

const APPROVAL: Record<Approval['status'], Tone> = {
  SUBMITTED: 'info',
  UNDER_REVIEW: 'accent',
  NEEDS_CLARIFICATION: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  EXECUTED: 'success',
  STALE: 'warning',
}

export function ApprovalStatusBadge({ status }: { status: Approval['status'] }) {
  return <Badge tone={APPROVAL[status]}>{titleCase(status)}</Badge>
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Badge tone="neutral">{titleCase(category)}</Badge>
}

export function SlaSummary({ sla, compact }: { sla: Sla; compact?: boolean }) {
  return <SlaMeter percent={sla.percentElapsed} state={sla.state} remaining={sla.remaining} size={compact ? 'sm' : 'md'} />
}

export { slaTone }
