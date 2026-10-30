import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from './cn'
import type { Tone } from './Badge'

const TONE_TEXT: Record<Tone, string> = {
  neutral: 'text-ink',
  accent: 'text-accent-ink',
  success: 'text-success-ink',
  warning: 'text-warning-ink',
  danger: 'text-danger-ink',
  info: 'text-info-ink',
}

const TONE_ICON: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-muted',
  accent: 'bg-accent-soft text-accent-ink',
  success: 'bg-success-soft text-success-ink',
  warning: 'bg-warning-soft text-warning-ink',
  danger: 'bg-danger-soft text-danger-ink',
  info: 'bg-info-soft text-info-ink',
}

export interface StatTileProps {
  label: string
  value: ReactNode
  hint?: string
  tone?: Tone
  icon?: ReactNode
  /** A short trend note. `good` says whether the direction is good news, so the colour is not guessed. */
  trend?: { direction: 'up' | 'down' | 'flat'; label: string; good?: boolean }
  className?: string
}

export function StatTile({ label, value, hint, tone = 'neutral', icon, trend, className }: StatTileProps) {
  const TrendIcon = trend?.direction === 'up' ? ArrowUpRight : trend?.direction === 'down' ? ArrowDownRight : ArrowRight
  return (
    <div className={cn('rounded-lg border border-line bg-surface p-4 shadow-card', className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-muted">{label}</p>
        {icon ? <span className={cn('grid size-9 shrink-0 place-items-center rounded-md', TONE_ICON[tone])}>{icon}</span> : null}
      </div>
      <p className={cn('mt-2 text-3xl font-semibold tracking-tight', TONE_TEXT[tone])}>{value}</p>
      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-muted">
        {trend ? (
          <span className={cn('inline-flex items-center gap-0.5 font-medium', trend.good === undefined ? 'text-muted' : trend.good ? 'text-success-ink' : 'text-danger-ink')}>
            <TrendIcon aria-hidden="true" className="size-3.5" />
            {trend.label}
          </span>
        ) : null}
        {hint ? <span>{hint}</span> : null}
      </div>
    </div>
  )
}
