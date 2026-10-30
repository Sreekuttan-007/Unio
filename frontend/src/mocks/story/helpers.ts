import type { Sla } from '@/types/domain'
import type { SlaState } from '@/ui'

/** All story times are relative to "now", so a demo always looks live whenever it is opened. */
export interface Clock {
  now: number
  /** minutes from now: negative is the past */
  at: (minutes: number) => string
}

export const makeClock = (now: number = Date.now()): Clock => ({ now, at: (minutes) => new Date(now + minutes * 60_000).toISOString() })

function duration(minutes: number): string {
  const total = Math.abs(Math.round(minutes))
  if (total < 60) return `${total} min`
  const hours = Math.floor(total / 60)
  const rest = total % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

export function sla(clock: Clock, state: SlaState, percentElapsed: number, minutesLeft: number): Sla {
  const remaining = state === 'MET' ? 'Closed within target' : state === 'PAUSED' ? 'Paused while waiting for parts' : minutesLeft >= 0 ? `${duration(minutesLeft)} left` : `overdue by ${duration(minutesLeft)}`
  return { state, percentElapsed, remaining, dueAt: clock.at(minutesLeft) }
}

export const rupees = (paise: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)

export const wait = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms))
