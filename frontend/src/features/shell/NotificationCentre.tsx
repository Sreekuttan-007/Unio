import { useState } from 'react'
import { Button, ListRow, NotificationBell, Sheet } from '@/ui'
import { ago } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useAction, useApi } from '../shared/useApi'

interface NotificationList {
  unread: number
  items: { id: string; title: string; body: string; read: boolean; at: string }[]
}

/** The bell and its sheet. Only the caller's own notifications are ever returned by the backend. */
export function NotificationCentre({ unread }: { unread: number }) {
  const [open, setOpen] = useState(false)
  const list = useApi<NotificationList>('/notifications', { enabled: open })
  const markAll = useAction<Record<string, never>, { marked: number }>('POST', '/notifications/read', ['/notifications', 'badges'])

  return (
    <>
      <NotificationBell unread={unread} onOpen={() => setOpen(true)} />
      <Sheet open={open} title="Notifications" onClose={() => setOpen(false)}>
        <QueryBoundary query={list} isEmpty={(data) => data.items.length === 0} emptyTitle="Nothing yet" emptyDescription="You are told here when something needs you or changes for you.">
          {(data) => (
            <div className="space-y-3">
              {data.unread > 0 ? <Button variant="secondary" compact loading={markAll.isPending} onClick={() => markAll.mutate({})}>Mark all as read</Button> : null}
              <div>
                {data.items.map((item) => (
                  <ListRow key={item.id} title={item.read ? item.title : `${item.title} (new)`} subtitle={item.body || undefined} meta={ago(item.at)} />
                ))}
              </div>
            </div>
          )}
        </QueryBoundary>
      </Sheet>
    </>
  )
}

