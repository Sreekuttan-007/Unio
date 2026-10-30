import { useState } from 'react'
import { Badge, Banner, Card, CardBody, CardHeader, CampusMap, ListRow, MapLegend, PageHeader, Sheet, type MapDecor, type MapMarker, type MapRegion, type RegionOverlay } from '@/ui'
import type { Priority } from '@/types/domain'
import { PriorityBadge } from '../shared/badges'
import { QueryBoundary } from '../shared/QueryBoundary'
import { useApi } from '../shared/useApi'

interface MapData {
  viewBox: { w: number; h: number }
  decor: MapDecor[]
  regions: (MapRegion & { entityId: string })[]
  overlays: Record<string, RegionOverlay>
  markers: MapMarker[]
  view: 'PUBLIC' | 'OPERATIONAL'
}

interface BuildingDetail {
  id: string
  name: string
  code: string
  kind: string
  status: string
  openingHours: string
  floors: number
  department: string
  assetCount: number | null
  roomCount: number
  rooms: { code: string; type: string; capacity: number; status: string; note: string | null }[]
  incidents: { id: string; title: string; priority: Priority; status: string }[]
}

const STATE_TONE = { OPEN: 'success', AFFECTED: 'warning', CLOSED: 'danger', MAINTENANCE: 'info' } as const

function BuildingPanel({ regionId }: { regionId: string }) {
  const detail = useApi<BuildingDetail>(`/campus/buildings/${regionId}`)
  return (
    <QueryBoundary query={detail}>
      {(building) => (
        <Card>
          <CardHeader title={building.name} description={`${building.code} · ${building.openingHours}`} action={<Badge tone={STATE_TONE[building.status as keyof typeof STATE_TONE] ?? 'neutral'}>{building.status.toLowerCase()}</Badge>} />
          <CardBody className="space-y-4 text-sm">
            <dl className="grid grid-cols-2 gap-3">
              <div><dt className="text-xs text-muted">Floors</dt><dd className="font-medium">{building.floors}</dd></div>
              <div><dt className="text-xs text-muted">Rooms</dt><dd className="font-medium">{building.roomCount}</dd></div>
              <div><dt className="text-xs text-muted">Owned by</dt><dd className="font-medium">{building.department}</dd></div>
              {building.assetCount !== null ? <div><dt className="text-xs text-muted">Tracked assets</dt><dd className="font-medium">{building.assetCount}</dd></div> : null}
            </dl>
            {building.incidents.length > 0 ? (
              <section aria-label="Open incidents">
                <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Open incidents</h3>
                <div className="-mx-5 border-t border-line">
                  {building.incidents.map((incident) => (
                    <ListRow key={incident.id} title={incident.title} subtitle={incident.id} trailing={<PriorityBadge priority={incident.priority} />} />
                  ))}
                </div>
              </section>
            ) : null}
            {building.rooms.length > 0 ? (
              <section aria-label="Rooms">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Rooms</h3>
                <ul className="flex flex-wrap gap-1.5">
                  {building.rooms.map((room) => (
                    <li key={room.code}>
                      <Badge tone={room.status === 'CLOSED' ? 'danger' : 'neutral'} className="tabular-nums">
                        {room.code}
                        {room.status === 'CLOSED' ? ' closed' : ''}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {building.rooms.length === 0 && building.assetCount === null ? <p className="text-muted">Detailed room and repair information is shown to campus staff only.</p> : null}
          </CardBody>
        </Card>
      )}
    </QueryBoundary>
  )
}

/** One map for every role. The server decides how much detail each role receives. */
export function CampusMapScreen({ title, description, initialSelected = null }: { title: string; description: string; initialSelected?: string | null }) {
  const map = useApi<MapData>('/campus/map', { refetchMs: 20_000 })
  const [selected, setSelected] = useState<string | null>(initialSelected)

  return (
    <div>
      <PageHeader title={title} description={description} />
      <QueryBoundary query={map}>
        {(data) => (
          <div className="space-y-4">
            {data.view === 'PUBLIC' ? <Banner tone="info" title="Public view">Closures and affected buildings are shown. Repair and staff detail is limited to campus staff.</Banner> : null}
            <div className="grid gap-4 2xl:grid-cols-[1fr_24rem]">
              <div className="space-y-3">
                <CampusMap viewBox={data.viewBox} decor={data.decor} regions={data.regions} overlays={data.overlays} markers={data.markers} selectedId={selected} onSelect={setSelected} />
                <MapLegend />
                {data.markers.length > 0 ? <p className="text-xs text-muted">Dots are open incidents. Red is P1, amber is P2.</p> : null}
              </div>
              {/* On a wide screen the details sit beside the map. Anywhere narrower they slide over it. */}
              <div className="hidden 2xl:block" aria-live="polite">
                {selected ? <BuildingPanel regionId={selected} /> : <Card><CardBody className="text-sm text-muted">Select a building to see its status, rooms and open incidents.</CardBody></Card>}
              </div>
              <div className="2xl:hidden">
                <Sheet open={selected !== null} title="Building" onClose={() => setSelected(null)}>
                  {selected ? <BuildingPanel regionId={selected} /> : null}
                </Sheet>
                {selected === null ? <p className="text-sm text-muted">Tap a building to see its status, rooms and open incidents.</p> : null}
              </div>
            </div>
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
