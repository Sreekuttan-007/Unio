import generated from '../fixtures/generated.json'
import type { MapDecor, MapRegion } from '@/ui'

/** The fictional campus, straight from the backend generator, so the mock map is the real layout. */
export interface CampusRoom {
  id: string
  code: string
  buildingId: string
  floorId: string
  type: string
  capacity: number
  features: string[]
  departmentId: string | null
  status: string
  bookable: boolean
}

export interface CampusBuilding {
  id: string
  code: string
  name: string
  kind: string
  departmentId: string | null
  floors: number
  mapRegionId: string
  status: string
  openingHours: string
  assetCount: number
}

interface CampusFixture {
  map: { version: number; viewBox: { w: number; h: number }; decor: MapDecor[]; regions: (MapRegion & { entityId: string })[] }
  buildings: CampusBuilding[]
  rooms: CampusRoom[]
  keyAssets: { id: string; name: string; category: string; buildingId: string; roomId: string | null; criticality: number }[]
  technicians: { id: string; userId: string; name: string; departmentId: string; skills: { code: string; level: number }[]; maxConcurrentTasks: number }[]
  faculty: { id: string; name: string; departmentId: string; kind: string }[]
  groups: { id: string; departmentId: string; size: number; homeRoomId: string }[]
  sessions: { id: string; courseName: string; kind: 'LECTURE' | 'PRACTICAL' | 'EXAM'; roomId: string; facultyId: string; studentGroup: string; headcount: number; start: string; end: string }[]
  items: { id: string; sku: string; name: string; category: string; unit: string; reorderThreshold: number; critical: boolean; unitCostPaise: number; onHand: number }[]
  history: { id: string; assetId: string | null; roomId: string | null; buildingId: string; category: string; summary: string; completedAt: string }[]
}

export const campus = (generated as unknown as { campus: CampusFixture }).campus

export const buildingById = (id: string) => campus.buildings.find((building) => building.id === id)
export const roomByCode = (code: string) => campus.rooms.find((room) => room.code === code)
export const regionIdOf = (buildingId: string) => buildingById(buildingId)?.mapRegionId ?? ''
export const departmentName = (id: string | null) =>
  ({ 'D-CSE': 'Computer Science', 'D-ECE': 'Electronics and Communication', 'D-ELEC': 'Electrical Maintenance', 'D-NET': 'Network Operations' })[id ?? ''] ?? 'Shared'

/** A point in the middle of a building on the map, for incident markers. */
export function regionCentre(regionId: string): { x: number; y: number } {
  const region = campus.map.regions.find((item) => item.regionId === regionId)
  return region ? { x: region.shape.x + region.shape.w / 2, y: region.shape.y + region.shape.h / 2 + 18 } : { x: 0, y: 0 }
}
