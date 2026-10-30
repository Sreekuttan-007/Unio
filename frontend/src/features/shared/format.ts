const LOCALE = 'en-IN'

export const clockTime = (iso: string) => new Date(iso).toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false })

export const shortDate = (iso: string) => new Date(iso).toLocaleDateString(LOCALE, { weekday: 'short', day: 'numeric', month: 'short' })

export const dateTime = (iso: string) => `${shortDate(iso)}, ${clockTime(iso)}`

export function ago(iso: string, now: number = Date.now()): string {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

export const money = (paise: number) => new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(paise / 100)

export const titleCase = (value: string) => value.toLowerCase().replace(/_/g, ' ').replace(/^\w/, (letter) => letter.toUpperCase())

/** yyyy-mm-dd for a date input, in local time. */
export const inputDate = (date: Date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
