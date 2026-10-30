import type { ReactNode } from 'react'
import { Badge } from './Badge'

export interface KanbanColumn {
  id: string
  title: string
  cards: { id: string; node: ReactNode }[]
}

/** Columns scroll sideways inside the board on a phone, so the page itself never overflows. */
export function Kanban({ columns, emptyLabel = 'Nothing here' }: { columns: KanbanColumn[]; emptyLabel?: string }) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 pb-2 lg:mx-0 lg:px-0">
      <div className="flex min-w-max gap-4">
        {columns.map((column) => (
          <section key={column.id} aria-label={column.title} className="w-72 shrink-0 rounded-lg bg-surface-2 p-3">
            <header className="mb-3 flex items-center justify-between px-1">
              <h3 className="text-sm font-semibold text-ink">{column.title}</h3>
              <Badge>{column.cards.length}</Badge>
            </header>
            <ul className="space-y-3">
              {column.cards.map((card) => (
                <li key={card.id}>{card.node}</li>
              ))}
              {column.cards.length === 0 ? <li className="px-1 py-6 text-center text-xs text-faint">{emptyLabel}</li> : null}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
