import type { ReactNode } from 'react'
import { cn } from './cn'

export interface Column<Row> {
  key: string
  header: string
  cell: (row: Row) => ReactNode
  className?: string
}

/** Scrolls sideways inside its card on a phone, so the page itself never overflows. */
export function DataTable<Row>({ columns, rows, rowKey, caption }: { columns: Column<Row>[]; rows: Row[]; rowKey: (row: Row) => string; caption: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
            {columns.map((column) => (
              <th key={column.key} scope="col" className={cn('px-4 py-3 font-semibold', column.className)}>{column.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-line last:border-0">
              {columns.map((column) => (
                <td key={column.key} className={cn('px-4 py-3 align-middle text-ink', column.className)}>{column.cell(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
