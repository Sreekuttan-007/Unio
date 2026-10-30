import { Bell } from 'lucide-react'

export interface NotificationBellProps {
  unread: number
  onOpen: () => void
}

/** The bell in the top bar. The count is text as well as a dot, so it never relies on colour. */
export function NotificationBell({ unread, onOpen }: NotificationBellProps) {
  const label = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
  return (
    <button type="button" aria-label={label} onClick={onOpen} className="relative grid size-11 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink">
      <Bell aria-hidden="true" className="size-5" />
      {unread > 0 ? (
        <span aria-hidden="true" className="absolute right-1 top-1 grid min-w-5 place-items-center rounded-full bg-danger-soft px-1 text-xs font-semibold text-danger-ink ring-1 ring-danger">
          {unread > 99 ? '99+' : unread}
        </span>
      ) : null}
    </button>
  )
}
