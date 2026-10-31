import { ArrowDown } from 'lucide-react'
import { Fragment } from 'react'
import { Badge, type Tone } from './Badge'
import { cn } from './cn'

export interface ImpactStep {
  id: string
  /** How far from the fault: 0 is the fault itself. */
  depth: number
  kind: string
  title: string
  detail?: string
  severity?: 'HIGH' | 'MEDIUM' | 'LOW'
  /** Why this follows from the previous step, in plain words. */
  reason?: string
}

const SEVERITY: Record<NonNullable<ImpactStep['severity']>, { tone: Tone; label: string }> = {
  HIGH: { tone: 'danger', label: 'High impact' },
  MEDIUM: { tone: 'warning', label: 'Medium impact' },
  LOW: { tone: 'info', label: 'Low impact' },
}

/** The explainable chain from a fault to everything it touches, drawn from stored relationships. */
export function ImpactChain({ steps }: { steps: ImpactStep[] }) {
  return (
    <ol className="space-y-1" aria-label="Impact chain">
      {steps.map((step, index) => (
        <Fragment key={step.id}>
          {index > 0 ? (
            <li aria-hidden="true" className="flex items-center gap-2 pl-5 text-xs text-faint" style={{ marginLeft: `${Math.min(step.depth, 4) * 0.75}rem` }}>
              <ArrowDown className="size-3.5" />
              {step.reason}
            </li>
          ) : null}
          <li style={{ marginLeft: `${Math.min(step.depth, 4) * 0.75}rem` }}>
            <div className={cn('flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 shadow-xs', index === 0 ? 'border-danger/60 bg-danger-soft' : 'border-line/70 bg-surface/90')}>
              <span className="rounded-sm bg-surface-3 px-2 py-0.5 text-[0.6875rem] font-semibold uppercase tracking-wide text-muted">{step.kind}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">{step.title}</p>
                {step.detail ? <p className="text-xs text-muted">{step.detail}</p> : null}
              </div>
              {step.severity ? <Badge tone={SEVERITY[step.severity].tone}>{SEVERITY[step.severity].label}</Badge> : null}
            </div>
          </li>
        </Fragment>
      ))}
    </ol>
  )
}
