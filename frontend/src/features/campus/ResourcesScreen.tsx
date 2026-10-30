import { Avatar, Badge, Card, CardHeader, DataTable, ListRow, PageHeader, StatTile, type Column } from '@/ui'
import type { TechnicianCard } from '@/types/domain'
import { titleCase } from '../shared/format'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

interface Resources {
  department: string
  rooms: { code: string; type: string; capacity: number; building: string; status: string }[]
  assets: { id: string; name: string; category: string; status: string }[]
  technicians: TechnicianCard[]
}

export function ResourcesScreen() {
  const resources = useApi<Resources>('/campus/resources')
  const columns: Column<Resources['rooms'][number]>[] = [
    { key: 'room', header: 'Room', cell: (room) => <span className="font-medium">{room.code}</span> },
    { key: 'type', header: 'Type', cell: (room) => titleCase(room.type) },
    { key: 'cap', header: 'Seats', className: 'text-right tabular-nums', cell: (room) => room.capacity },
    { key: 'building', header: 'Building', cell: (room) => room.building },
    { key: 'status', header: 'Status', cell: (room) => <Badge tone={room.status === 'CLOSED' ? 'danger' : 'success'}>{room.status === 'CLOSED' ? 'Closed: no power' : 'Open'}</Badge> },
  ]
  return (
    <div className="space-y-5">
      <PageHeader title="Resources" description="Rooms, key equipment, and the people who maintain them." />
      <QueryBoundary query={resources}>
        {(data) => (
          <>
            <div className="grid gap-4 sm:grid-cols-4">
              <StatTile label="Rooms" value={data.rooms.length} />
              <StatTile label="Closed now" value={data.rooms.filter((room) => room.status === 'CLOSED').length} tone="danger" />
              <StatTile label="Key assets" value={data.assets.length} />
              <StatTile label="Assets with a fault" value={data.assets.filter((asset) => asset.status === 'FAULT').length} tone="warning" />
            </div>
            <Card><CardHeader title={`${data.department} rooms`} /><DataTable caption="Rooms" columns={columns} rows={data.rooms} rowKey={(room) => room.code} /></Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader title="Key equipment" />
                {data.assets.map((asset) => <ListRow key={asset.id} title={asset.name} subtitle={`${asset.id} · ${titleCase(asset.category)}`} trailing={<Badge tone={asset.status === 'FAULT' ? 'danger' : 'success'}>{asset.status === 'FAULT' ? 'Fault' : 'Working'}</Badge>} />)}
              </Card>
              <Card>
                <CardHeader title="Technicians you can call on" description="Skills and workload, so you know who can take the work" />
                {data.technicians.map((tech) => (
                  <ListRow key={tech.id} leading={<Avatar initials={tech.name.split(' ').map((part) => part[0]).join('').slice(0, 2)} size="sm" />} title={tech.name} subtitle={tech.skills.map((skill) => `${titleCase(skill.code)} L${skill.level}`).join(', ')} trailing={<Badge tone={tech.availability === 'SICK' ? 'danger' : tech.availability === 'AVAILABLE' ? 'success' : 'info'}>{tech.availability === 'SICK' ? 'Off sick' : `${tech.openTasks} of ${tech.maxTasks}`}</Badge>} />
                ))}
              </Card>
            </div>
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
