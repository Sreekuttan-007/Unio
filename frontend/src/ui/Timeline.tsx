import type { ReactNode } from 'react'
import { cn } from './cn'
import type { Tone } from './Badge'

const DOT: Record<Tone, string> = {
  neutral: 'bg-line-strong',
  accent: 'bg-accent',
  success: 'bg-pistachio',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-lavender',
}

export interface TimelineEvent {
  id: string
  title: string
  detail?: string
  /** Already formatted for people, such as "09:12" or "2 min ago". */
  when: string
  tone?: Tone
  extra?: ReactNode
}

export function Timeline({ events, className }: { events: TimelineEvent[]; className?: string }) {
  return (
    <ol className={cn('relative space-y-5 border-l border-line/60 pl-6', className)}>
      {events.map((event) => (
        <li key={event.id} className="relative">
          <span aria-hidden="true" className={cn('absolute -left-[1.9rem] top-1.5 size-3 rounded-full ring-4 ring-surface', DOT[event.tone ?? 'neutral'])} />
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <p className="text-sm font-medium text-ink">{event.title}</p>
            <time className="text-xs text-muted">{event.when}</time>
          </div>
          {event.detail ? <p className="mt-0.5 text-sm text-muted">{event.detail}</p> : null}
          {event.extra}
        </li>
      ))}
    </ol>
  )
}
