import { Badge, BarList, Card, CardBody, CardHeader, ColumnChart, DonutChart, ListRow, PageHeader, Sparkline, StatTile, type Datum } from '@/ui'
import type { AnalyticsOverview } from '@/types/domain'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

const toDatum = (items: { label: string; value: number }[], suffix = '', tone?: Datum['tone']): Datum[] => items.map((item) => ({ ...item, suffix, tone }))

export function AnalyticsScreen({ title, description }: { title: string; description: string }) {
  const overview = useApi<AnalyticsOverview>('/analytics/overview')
  return (
    <div className="space-y-5">
      <PageHeader title={title} description={description} />
      <QueryBoundary query={overview}>
        {(data) => (
          <>
            <div className="grid gap-4 sm:grid-cols-4">
              <StatTile label="Open requests" value={data.open.total} tone="accent" />
              <StatTile label="SLA compliance" value={`${data.sla.rate}%`} tone={data.sla.rate >= 90 ? 'success' : 'warning'} trend={{ direction: 'down', label: '4 points this week', good: false }} />
              <StatTile label="Parts out of stock" value={data.shortages.length} tone="danger" hint={`${data.shortages.reduce((sum, item) => sum + item.blocked, 0)} work blocked`} />
              <StatTile label="Recurring faults" value={data.recurring.length} tone="warning" hint="Same asset, repeat visits" />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader title="Open requests by status" />
                <CardBody><DonutChart centre={String(data.open.total)} caption="open" slices={data.open.byStatus.map((item, index) => ({ ...item, tone: (['info', 'accent', 'success', 'warning', 'danger'] as const)[index % 5]! }))} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="Open requests by type" />
                <CardBody><BarList data={toDatum(data.open.byCategory)} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="SLA compliance" description="Share of work finished within target" action={<Sparkline values={data.sla.trend} tone="success" />} />
                <CardBody><BarList data={data.sla.byPriority.map((item) => ({ ...item, suffix: '%', tone: item.value >= 90 ? 'success' : item.value >= 80 ? 'warning' : 'danger' }))} max={100} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="Reports this week" description="Wednesday is today's disruption" />
                <CardBody><ColumnChart data={data.daily.map((item, index) => ({ ...item, tone: index === data.daily.length - 1 ? 'danger' : 'accent' }))} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="Room use" description="Booked hours as a share of available hours" />
                <CardBody><BarList data={toDatum(data.utilisation.rooms, '%')} max={100} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="Technician utilisation" description="Assigned hours as a share of shift hours" />
                <CardBody><BarList data={data.utilisation.technicians.map((item) => ({ ...item, suffix: '%', tone: item.value > 80 ? 'danger' : item.value > 60 ? 'warning' : 'success' }))} max={100} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="Shortages" description="Parts at or below zero" />
                {data.shortages.map((item) => <ListRow key={item.name} title={item.name} subtitle={`Reorder level ${item.threshold}`} trailing={item.blocked ? <Badge tone="danger">Blocks {item.blocked} work</Badge> : <Badge tone="warning">{item.onHand === 0 ? 'Out of stock' : `${item.onHand} left`}</Badge>} />)}
              </Card>
              <Card>
                <CardHeader title="Recurring incidents" description="The same thing breaking again" />
                {data.recurring.map((item) => <ListRow key={`${item.name}-${item.location}`} title={item.name} subtitle={`${item.location} · last ${item.last}`} trailing={<Badge tone={item.count >= 5 ? 'danger' : 'warning'}>{item.count} times</Badge>} />)}
              </Card>
            </div>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
