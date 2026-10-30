import { cn } from './cn'
import type { Tone } from './Badge'

const FILL: Record<Tone, string> = {
  neutral: 'fill-line-strong',
  accent: 'fill-accent',
  success: 'fill-success',
  warning: 'fill-warning',
  danger: 'fill-danger',
  info: 'fill-info',
}

const BAR: Record<Tone, string> = {
  neutral: 'bg-line-strong',
  accent: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
}

const STROKE: Record<Tone, string> = {
  neutral: 'stroke-line-strong',
  accent: 'stroke-accent',
  success: 'stroke-success',
  warning: 'stroke-warning',
  danger: 'stroke-danger',
  info: 'stroke-info',
}

export interface Datum {
  label: string
  value: number
  tone?: Tone
  /** Shown after the value, such as "%" or " h". */
  suffix?: string
}

/** Horizontal bars with the value written out, so no chart ever depends on colour or hover. */
export function BarList({ data, max, className }: { data: Datum[]; max?: number; className?: string }) {
  const top = max ?? Math.max(1, ...data.map((item) => item.value))
  return (
    <ul className={cn('space-y-3', className)}>
      {data.map((item) => (
        <li key={item.label}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 truncate text-ink">{item.label}</span>
            <span className="shrink-0 font-medium tabular-nums text-ink">
              {item.value}
              {item.suffix ?? ''}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-3" role="presentation">
            <div className={cn('h-full rounded-full', BAR[item.tone ?? 'accent'])} style={{ width: `${Math.min(100, (item.value / top) * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Vertical columns for a short series, such as the last seven days. */
export function ColumnChart({ data, height = 140, className }: { data: Datum[]; height?: number; className?: string }) {
  const top = Math.max(1, ...data.map((item) => item.value))
  const width = 100
  const slot = width / data.length
  return (
    <figure className={className}>
      <svg viewBox={`0 0 ${width} ${height / 2}`} role="img" aria-label={data.map((item) => `${item.label}: ${item.value}`).join(', ')} className="w-full" style={{ height }}>
        {data.map((item, index) => {
          const barHeight = (item.value / top) * (height / 2 - 10)
          return (
            <g key={item.label}>
              <rect x={index * slot + slot * 0.18} y={height / 2 - 8 - barHeight} width={slot * 0.64} height={barHeight} rx={1.5} className={FILL[item.tone ?? 'accent']} />
              <text x={index * slot + slot / 2} y={height / 2 - 1} textAnchor="middle" fontSize={4} className="fill-muted">
                {item.label}
              </text>
            </g>
          )
        })}
      </svg>
    </figure>
  )
}

export interface Slice {
  label: string
  value: number
  tone: Tone
}

/** A ring with a centre label and a legend that carries the numbers. */
export function DonutChart({ slices, centre, caption, className }: { slices: Slice[]; centre: string; caption?: string; className?: string }) {
  const total = Math.max(1, slices.reduce((sum, slice) => sum + slice.value, 0))
  const radius = 42
  const circumference = 2 * Math.PI * radius
  let offset = 0
  return (
    <div className={cn('flex flex-wrap items-center gap-6', className)}>
      <svg viewBox="0 0 120 120" role="img" aria-label={slices.map((slice) => `${slice.label}: ${slice.value}`).join(', ')} className="size-36 shrink-0 -rotate-90">
        <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="14" className="stroke-surface-3" />
        {slices.map((slice) => {
          const length = (slice.value / total) * circumference
          const dash = `${Math.max(0, length - 1.5)} ${circumference - Math.max(0, length - 1.5)}`
          const node = (
            <circle key={slice.label} cx="60" cy="60" r={radius} fill="none" strokeWidth="14" strokeDasharray={dash} strokeDashoffset={-offset} className={STROKE[slice.tone]} />
          )
          offset += length
          return node
        })}
        <g className="rotate-90 origin-center">
          <text x="60" y="58" textAnchor="middle" fontSize="20" fontWeight="600" className="fill-ink">{centre}</text>
          {caption ? <text x="60" y="74" textAnchor="middle" fontSize="9" className="fill-muted">{caption}</text> : null}
        </g>
      </svg>
      <ul className="min-w-40 flex-1 space-y-2 text-sm">
        {slices.map((slice) => (
          <li key={slice.label} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-ink">
              <span aria-hidden="true" className={cn('size-2.5 rounded-full', BAR[slice.tone])} />
              {slice.label}
            </span>
            <span className="font-medium tabular-nums text-ink">{slice.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Sparkline({ values, tone = 'accent', className }: { values: number[]; tone?: Tone; className?: string }) {
  const max = Math.max(...values)
  const min = Math.min(...values)
  const span = Math.max(1, max - min)
  const points = values.map((value, index) => `${(index / Math.max(1, values.length - 1)) * 100},${28 - ((value - min) / span) * 24}`).join(' ')
  return (
    <svg viewBox="0 0 100 32" role="img" aria-label={`Trend: ${values.join(', ')}`} className={cn('h-8 w-24', className)}>
      <polyline points={points} fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={STROKE[tone]} />
    </svg>
  )
}

export function ProgressBar({ value, tone = 'accent', label, className }: { value: number; tone?: Tone; label?: string; className?: string }) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div className={className}>
      {label ? (
        <div className="mb-1 flex justify-between text-xs text-muted">
          <span>{label}</span>
          <span className="tabular-nums">{Math.round(clamped)}%</span>
        </div>
      ) : null}
      <div className="h-2 overflow-hidden rounded-full bg-surface-3" role="progressbar" aria-valuenow={Math.round(clamped)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={cn('h-full rounded-full', BAR[tone])} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  )
}
