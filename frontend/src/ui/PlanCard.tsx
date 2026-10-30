import { Check, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge } from './Badge'
import { cn } from './cn'

export interface PlanMetric {
  label: string
  value: string
}

export interface PlanFinding {
  severity: 'HARD' | 'SOFT'
  message: string
}

export interface PlanCardProps {
  title: string
  summary: string
  feasible: boolean
  recommended?: boolean
  metrics: PlanMetric[]
  findings: PlanFinding[]
  action?: ReactNode
}

/** One recovery option in the simulator: whether it is allowed, what it costs, and exactly why not. */
export function PlanCard({ title, summary, feasible, recommended, metrics, findings, action }: PlanCardProps) {
  return (
    <article className={cn('flex flex-col rounded-lg border bg-surface p-5 shadow-card', recommended ? 'border-accent ring-2 ring-accent-soft' : 'border-line')} aria-label={title}>
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        {recommended ? <Badge tone="accent">Recommended</Badge> : null}
        <Badge tone={feasible ? 'success' : 'danger'} icon={feasible ? <Check aria-hidden="true" className="size-3" /> : <X aria-hidden="true" className="size-3" />}>
          {feasible ? 'Allowed' : 'Blocked'}
        </Badge>
      </header>
      <p className="mt-2 text-sm text-muted">{summary}</p>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <dt className="text-xs text-muted">{metric.label}</dt>
            <dd className="font-medium text-ink">{metric.value}</dd>
          </div>
        ))}
      </dl>
      {findings.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {findings.map((finding) => (
            <li key={finding.message} className={cn('rounded-md px-3 py-2 text-sm', finding.severity === 'HARD' ? 'bg-danger-soft text-danger-ink' : 'bg-warning-soft text-warning-ink')}>
              <span className="font-semibold">{finding.severity === 'HARD' ? 'Blocks: ' : 'Warns: '}</span>
              {finding.message}
            </li>
          ))}
        </ul>
      ) : null}
      {action ? <div className="mt-auto pt-5">{action}</div> : null}
    </article>
  )
}
