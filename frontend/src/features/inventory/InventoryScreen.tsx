import { useState } from 'react'
import { Badge, Banner, Card, DataTable, PageHeader, SegmentedControl, StatTile, type Column } from '@/ui'
import type { StockRow } from '@/types/domain'
import { titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

type Filter = 'all' | 'low' | 'out' | 'critical'

const STATUS = { OK: 'success', LOW: 'warning', OUT: 'danger' } as const
const STATUS_LABEL = { OK: 'In stock', LOW: 'Running low', OUT: 'Out of stock' } as const

export function InventoryScreen({ title, description, master = false }: { title: string; description: string; master?: boolean }) {
  const stock = useApi<StockRow[]>('/inventory/items')
  const [filter, setFilter] = useState<Filter>('all')

  const columns: Column<StockRow>[] = [
    { key: 'item', header: 'Item', cell: (row) => (<div><p className="font-medium">{row.name}</p><p className="text-xs text-muted">{row.sku} · {titleCase(row.category)}</p></div>) },
    { key: 'onHand', header: 'On hand', className: 'text-right tabular-nums', cell: (row) => `${row.onHand} ${row.unit}` },
    { key: 'reserved', header: 'Reserved', className: 'text-right tabular-nums', cell: (row) => row.reserved },
    { key: 'available', header: 'Available', className: 'text-right tabular-nums font-semibold', cell: (row) => row.available },
    { key: 'threshold', header: master ? 'Reorder at' : 'Reorder level', className: 'text-right tabular-nums', cell: (row) => row.threshold },
    {
      key: 'status',
      header: 'Status',
      cell: (row) => (
        <span className="flex flex-wrap gap-1.5">
          <Badge tone={STATUS[row.status]}>{STATUS_LABEL[row.status]}</Badge>
          {row.critical ? <Badge tone="accent">Critical part</Badge> : null}
          {row.blockedWorkOrders > 0 ? <Badge tone="danger">Blocks {row.blockedWorkOrders} work</Badge> : null}
        </span>
      ),
    },
  ]

  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} actions={<SegmentedControl label="Filter" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'All' }, { value: 'low', label: 'Low' }, { value: 'out', label: 'Out' }, { value: 'critical', label: 'Critical' }]} />} />
      <QueryBoundary query={stock} isEmpty={(rows) => rows.length === 0} emptyTitle="No stock items">
        {(rows) => {
          const blocked = rows.reduce((sum, row) => sum + row.blockedWorkOrders, 0)
          const visible = rows.filter((row) => (filter === 'low' ? row.status === 'LOW' : filter === 'out' ? row.status === 'OUT' : filter === 'critical' ? row.critical : true))
          return (
            <>
              {blocked > 0 ? <Banner tone="danger" title={`${blocked} work ${blocked === 1 ? 'order is' : 'orders are'} blocked by a shortage`}>The work is flagged blocked automatically, and a purchase request can be raised against it.</Banner> : null}
              <div className="grid gap-4 sm:grid-cols-4">
                <StatTile label="Items" value={rows.length} />
                <StatTile label="Out of stock" value={rows.filter((row) => row.status === 'OUT').length} tone="danger" />
                <StatTile label="Running low" value={rows.filter((row) => row.status === 'LOW').length} tone="warning" />
                <StatTile label="Reserved units" value={rows.reduce((sum, row) => sum + row.reserved, 0)} tone="accent" hint="Held for work orders" />
              </div>
              <Card><DataTable caption={title} columns={columns} rows={visible} rowKey={(row) => row.id} /></Card>
            </>
          )
        }}
      </QueryBoundary>
    </div>
  )
}
