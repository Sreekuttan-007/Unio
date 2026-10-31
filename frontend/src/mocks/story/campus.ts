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

export const SITE_MAP_BUILDINGS: CampusBuilding[] = [
  { id: 'BMS-12', code: 'BMS-12', name: 'New BMS Block', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 5, mapRegionId: 'BMS-12', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 24 },
  { id: 'BLK-13A', code: 'BLK-13A', name: 'Block 13 (North)', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 4, mapRegionId: 'BLK-13A', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 16 },
  { id: 'SRMIST-ADMIN', code: 'SRMIST-ADM', name: 'SRMIST Admin Block', kind: 'ADMINISTRATIVE', departmentId: null, floors: 6, mapRegionId: 'SRMIST-ADMIN', status: 'OPEN', openingHours: '08:30 - 17:30', assetCount: 38 },
  { id: 'BLK-13B', code: 'BLK-13B', name: 'Block 13 (South)', kind: 'ACADEMIC', departmentId: 'D-ECE', floors: 4, mapRegionId: 'BLK-13B', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 14 },
  { id: 'PG-1', code: 'PG-1', name: 'PG Block 1', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 4, mapRegionId: 'PG-1', status: 'OPEN', openingHours: '08:00 - 19:00', assetCount: 22 },
  { id: 'PG-2', code: 'PG-2', name: 'PG Block 2', kind: 'ACADEMIC', departmentId: 'D-ECE', floors: 4, mapRegionId: 'PG-2', status: 'OPEN', openingHours: '08:00 - 19:00', assetCount: 20 },
  { id: 'ELEC-1', code: 'ELEC-1', name: 'Electronics Block 1', kind: 'ACADEMIC', departmentId: 'D-ECE', floors: 3, mapRegionId: 'ELEC-1', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 18 },
  { id: 'ELEC-2', code: 'ELEC-2', name: 'Electronics Block 2', kind: 'ACADEMIC', departmentId: 'D-ECE', floors: 3, mapRegionId: 'ELEC-2', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 19 },
  { id: 'EEC-MAIN', code: 'EEC-MAIN', name: 'SRM Easwari Engineering College (EEC) Main Block', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 5, mapRegionId: 'EEC-MAIN', status: 'OPEN', openingHours: '08:00 - 18:30', assetCount: 45 },
  { id: 'PGCM-18', code: 'PGCM-18', name: 'PG, Civil & Mechanical Block', kind: 'ACADEMIC', departmentId: 'D-ELEC', floors: 4, mapRegionId: 'PGCM-18', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 30 },
  { id: 'ACAD-1', code: 'ACAD-1', name: 'Academic Block 1', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 4, mapRegionId: 'ACAD-1', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 25 },
  { id: 'ACAD-2', code: 'ACAD-2', name: 'Academic Block 2', kind: 'ACADEMIC', departmentId: 'D-ECE', floors: 4, mapRegionId: 'ACAD-2', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 21 },
  { id: 'ACAD-4', code: 'ACAD-4', name: 'Academic Block 4', kind: 'ACADEMIC', departmentId: 'D-NET', floors: 4, mapRegionId: 'ACAD-4', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 28 },
  { id: 'GH', code: 'GH', name: 'General Hospital', kind: 'HOSPITAL', departmentId: null, floors: 6, mapRegionId: 'GH', status: 'OPEN', openingHours: '24 Hours', assetCount: 85 },
  { id: 'SRM-PRIME', code: 'SRM-PRIME', name: 'General Hospital / SRM Prime Hospital', kind: 'HOSPITAL', departmentId: null, floors: 7, mapRegionId: 'SRM-PRIME', status: 'OPEN', openingHours: '24 Hours', assetCount: 92 },
  { id: 'DENTAL-COL', code: 'DENTAL-COL', name: 'SRM Dental College', kind: 'ACADEMIC', departmentId: null, floors: 4, mapRegionId: 'DENTAL-COL', status: 'OPEN', openingHours: '08:30 - 17:00', assetCount: 42 },
  { id: 'BLK-10', code: 'BLK-10', name: 'Block 10', kind: 'ACADEMIC', departmentId: null, floors: 3, mapRegionId: 'BLK-10', status: 'OPEN', openingHours: '08:30 - 17:00', assetCount: 15 },
  { id: 'DENTAL-HOSP', code: 'DENTAL-HOSP', name: 'Dental Hospital', kind: 'HOSPITAL', departmentId: null, floors: 5, mapRegionId: 'DENTAL-HOSP', status: 'OPEN', openingHours: '08:00 - 20:00', assetCount: 54 },
  { id: 'BOYS-8', code: 'BOYS-8', name: 'Boys Hostel', kind: 'RESIDENTIAL', departmentId: null, floors: 6, mapRegionId: 'BOYS-8', status: 'OPEN', openingHours: '06:00 - 21:30', assetCount: 16 },
  { id: 'BLK-9', code: 'BLK-9', name: 'Block 9 Hostel', kind: 'RESIDENTIAL', departmentId: null, floors: 5, mapRegionId: 'BLK-9', status: 'OPEN', openingHours: '06:00 - 21:30', assetCount: 14 },
  { id: 'LADIES-20', code: 'LADIES-20', name: 'Hostel Block 20', kind: 'RESIDENTIAL', departmentId: null, floors: 6, mapRegionId: 'LADIES-20', status: 'OPEN', openingHours: '06:00 - 21:00', assetCount: 18 },
  { id: 'CHELLAMMAL-21', code: 'CHELLAMMAL-21', name: 'Chellammal Ladies Hostel', kind: 'RESIDENTIAL', departmentId: null, floors: 5, mapRegionId: 'CHELLAMMAL-21', status: 'OPEN', openingHours: '06:00 - 21:00', assetCount: 17 },
  { id: 'SIVASAKTHI', code: 'SIVASAKTHI', name: 'Sivasakthi Ladies Hostel', kind: 'RESIDENTIAL', departmentId: null, floors: 5, mapRegionId: 'SIVASAKTHI', status: 'OPEN', openingHours: '06:00 - 21:00', assetCount: 15 },
  { id: 'IST-8', code: 'IST-8', name: 'Institute of Science & Technology', kind: 'ACADEMIC', departmentId: 'D-CSE', floors: 5, mapRegionId: 'IST-8', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 32 },
  { id: 'WORKSHOP', code: 'WORKSHOP', name: 'Workshop', kind: 'UTILITY', departmentId: 'D-ELEC', floors: 2, mapRegionId: 'WORKSHOP', status: 'CLOSED', openingHours: '08:00 - 17:00', assetCount: 22 },
  { id: 'BLK-3', code: 'BLK-3', name: 'Block 3', kind: 'COMMONS', departmentId: null, floors: 4, mapRegionId: 'BLK-3', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 12 },
  { id: 'BLK-23N', code: 'BLK-23N', name: 'Om Vinayaga Hostel (Block 23N)', kind: 'RESIDENTIAL', departmentId: null, floors: 4, mapRegionId: 'BLK-23N', status: 'OPEN', openingHours: '06:00 - 21:30', assetCount: 11 },
  { id: 'BLK-23S', code: 'BLK-23S', name: 'Block 23 South', kind: 'COMMONS', departmentId: null, floors: 2, mapRegionId: 'BLK-23S', status: 'OPEN', openingHours: '08:00 - 18:00', assetCount: 8 },
  { id: 'LAWN', code: 'LAWN', name: 'SRMIST Lawn', kind: 'GREENERY', departmentId: null, floors: 0, mapRegionId: 'LAWN', status: 'OPEN', openingHours: '06:00 - 22:00', assetCount: 0 },
  { id: 'EEC-COURT', code: 'EEC-COURT', name: 'EEC Courtyard', kind: 'GREENERY', departmentId: null, floors: 0, mapRegionId: 'EEC-COURT', status: 'OPEN', openingHours: '07:00 - 20:00', assetCount: 0 },
  { id: 'OAT', code: 'OAT', name: 'Open Air Theatre (OAT)', kind: 'COMMONS', departmentId: null, floors: 1, mapRegionId: 'OAT', status: 'OPEN', openingHours: '08:00 - 21:00', assetCount: 8 },
  { id: 'SPORTS', code: 'SPORTS', name: 'EEC Playground / Sports Complex', kind: 'SPORTS', departmentId: null, floors: 2, mapRegionId: 'SPORTS', status: 'OPEN', openingHours: '06:00 - 20:00', assetCount: 14 },
]

export const buildingById = (id: string) =>
  campus.buildings.find((building) => building.id === id || building.mapRegionId === id) ??
  SITE_MAP_BUILDINGS.find((building) => building.id === id || building.mapRegionId === id)

export const roomByCode = (code: string) => campus.rooms.find((room) => room.code === code)
export const regionIdOf = (buildingId: string) => buildingById(buildingId)?.mapRegionId ?? ''
export const departmentName = (id: string | null) =>
  ({ 'D-CSE': 'Computer Science', 'D-ECE': 'Electronics and Communication', 'D-ELEC': 'Electrical Maintenance', 'D-NET': 'Network Operations' })[id ?? ''] ?? 'Shared'

const SITE_MAP_CENTRES: Record<string, { x: number; y: number }> = {
  'BMS-12': { x: 1025, y: 440 },
  'BLK-13A': { x: 980, y: 337 },
  'SRMIST-ADMIN': { x: 1080, y: 356 },
  'BLK-13B': { x: 938, y: 575 },
  'PG-1': { x: 1035, y: 548 },
  'PG-2': { x: 1033, y: 614 },
  'ELEC-1': { x: 695, y: 576 },
  'ELEC-2': { x: 819, y: 572 },
  'UNK-T2': { x: 846, y: 523 },
  'EEC-MAIN': { x: 413, y: 530 },
  'UNK-T1': { x: 298, y: 439 },
  'PGCM-18': { x: 642, y: 855 },
  'UNK-T3': { x: 542, y: 798 },
  'ACAD-1': { x: 1381, y: 684 },
  'ACAD-2': { x: 1459, y: 664 },
  'ACAD-4': { x: 1202, y: 779 },
  'GH': { x: 1177, y: 555 },
  'SRM-PRIME': { x: 1272, y: 569 },
  'DENTAL-COL': { x: 1007, y: 676 },
  'BLK-10': { x: 953, y: 722 },
  'DENTAL-HOSP': { x: 1010, y: 802 },
  'UNK-M1': { x: 978, y: 892 },
  'BOYS-8': { x: 1221, y: 245 },
  'BLK-9': { x: 1228, y: 360 },
  'UNK-H1': { x: 1385, y: 210 },
  'LADIES-20': { x: 169, y: 714 },
  'CHELLAMMAL-21': { x: 192, y: 822 },
  'SIVASAKTHI': { x: 339, y: 820 },
  'UNK-H2': { x: 324, y: 701 },
  'IST-8': { x: 1410, y: 373 },
  'UNK-C1': { x: 1377, y: 255 },
  'WORKSHOP': { x: 1423, y: 143 },
  'BLK-3': { x: 1279, y: 772 },
  'BLK-23N': { x: 257, y: 597 },
  'BLK-23S': { x: 173, y: 635 },
  'LAWN': { x: 1029, y: 233 },
  'EEC-COURT': { x: 409, y: 534 },
  'OAT': { x: 579, y: 750 },
  'SPORTS': { x: 1544, y: 685 },
  'bld-arb': { x: 413, y: 530 },
  'bld-bhb': { x: 1381, y: 684 },
  'bld-rmb': { x: 1459, y: 664 },
  'bld-rlb': { x: 1202, y: 779 },
  'bld-lib': { x: 1035, y: 548 },
  'bld-adm': { x: 1080, y: 356 },
  'bld-caf': { x: 1544, y: 685 },
  'bld-klh': { x: 1221, y: 245 },
}

/** A point in the middle of a building on the map, for incident markers. */
export function regionCentre(regionId: string): { x: number; y: number } {
  if (SITE_MAP_CENTRES[regionId]) return SITE_MAP_CENTRES[regionId]
  const region = campus.map.regions.find((item) => item.regionId === regionId)
  return region ? { x: region.shape.x + region.shape.w / 2, y: region.shape.y + region.shape.h / 2 + 18 } : { x: 800, y: 600 }
}
