import type { ReactNode } from 'react'

export interface HeaderStat {
  label: string
  value: string | number
}

export function PageHeader({
  title,
  description,
  eyebrow,
  stats,
  actions,
}: {
  title: string
  description?: string
  eyebrow?: string
  stats?: HeaderStat[]
  actions?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-accent-ink">{eyebrow}</p>
        ) : null}
        <h1 className="text-2xl font-bold tracking-tight text-ink">{title}</h1>
        {description ? <p className="mt-1 max-w-prose text-sm text-muted">{description}</p> : null}
      </div>
      <div className="flex flex-wrap items-center gap-6">
        {stats && stats.length > 0 ? (
          <div className="flex items-center gap-6">
            {stats.map((stat) => (
              <div key={stat.label} className="text-left">
                <p className="text-xs font-medium text-muted">{stat.label}</p>
                <div className="flex items-center gap-1">
                  <span className="text-2xl font-bold tracking-tight text-ink tabular-nums">{stat.value}</span>
                  <span className="text-xs text-muted">↗</span>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        {actions}
      </div>
    </header>
  )
}
