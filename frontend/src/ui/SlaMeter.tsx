import { cn } from './cn'
import type { Tone } from './Badge'

export type SlaState = 'ON_TRACK' | 'AT_RISK' | 'BREACHED' | 'PAUSED' | 'MET'

const STATE: Record<SlaState, { label: string; tone: Tone }> = {
  ON_TRACK: { label: 'On track', tone: 'success' },
  AT_RISK: { label: 'At risk', tone: 'warning' },
  BREACHED: { label: 'Breached', tone: 'danger' },
  PAUSED: { label: 'Paused', tone: 'info' },
  MET: { label: 'Met', tone: 'success' },
}

const STROKE: Record<Tone, string> = {
  neutral: 'stroke-line-strong',
  accent: 'stroke-accent',
  success: 'stroke-success',
  warning: 'stroke-warning',
  danger: 'stroke-danger',
  info: 'stroke-info',
}

export function slaTone(state: SlaState): Tone {
  return STATE[state].tone
}

/** A ring showing time used, with the state written beside it so colour is never the only signal. */
export function SlaMeter({ percent, state, remaining, size = 'md' }: { percent: number; state: SlaState; remaining: string; size?: 'sm' | 'md' }) {
  const { label, tone } = STATE[state]
  const radius = 15.9
  const dash = `${Math.min(100, Math.max(0, percent))} ${100 - Math.min(100, Math.max(0, percent))}`
  return (
    <div className="flex items-center gap-3" data-testid="sla-meter">
      <svg viewBox="0 0 36 36" role="img" aria-label={`${label}, ${Math.round(percent)} percent of the time used`} className={cn('-rotate-90 shrink-0', size === 'md' ? 'size-14' : 'size-10')}>
        <circle cx="18" cy="18" r={radius} fill="none" strokeWidth="3.5" className="stroke-surface-3" />
        <circle cx="18" cy="18" r={radius} fill="none" strokeWidth="3.5" strokeLinecap="round" strokeDasharray={dash} pathLength={100} className={STROKE[tone]} />
      </svg>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-ink">{label}</p>
        <p className="text-xs text-muted">{remaining}</p>
      </div>
    </div>
  )
}
