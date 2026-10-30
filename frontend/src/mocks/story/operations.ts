import type { AnalyticsOverview, BookingRow, SlaRow, TechnicianCard, TodaySession, WorkOrder } from '@/types/domain'
import { campus, departmentName } from './campus'
import { sla, type Clock } from './helpers'

const TECH_ACTIONS = {
  ASSIGNED: [{ key: 'workorder.accept', label: 'Accept' }, { key: 'workorder.decline', label: 'Decline' }],
  ACCEPTED: [{ key: 'workorder.start', label: 'Start work' }],
  IN_PROGRESS: [{ key: 'workorder.block', label: 'Report a blocker' }, { key: 'workorder.complete', label: 'Complete' }],
  BLOCKED: [{ key: 'workorder.request-reassign', label: 'Ask for a replacement' }],
} as const

export function actionsFor(status: WorkOrder['status']): Pick<WorkOrder, 'availableActions' | 'unavailableActions'> {
  const available = [...(TECH_ACTIONS[status as keyof typeof TECH_ACTIONS] ?? [])]
  const unavailable =
    status === 'BLOCKED'
      ? [{ key: 'workorder.complete', label: 'Complete', reason: 'Blocked on parts. The reservation is not yet fulfilled.' }]
      : status === 'ASSIGNED'
        ? [{ key: 'workorder.complete', label: 'Complete', reason: 'Accept and start the work first.' }]
        : []
  return { availableActions: available, unavailableActions: unavailable }
}

export function buildWorkOrders(clock: Clock): WorkOrder[] {
  const { at } = clock
  const make = (wo: Omit<WorkOrder, 'availableActions' | 'unavailableActions'>): WorkOrder => ({ ...wo, ...actionsFor(wo.status) })
  return [
    make({
      id: 'WO-212',
      incidentId: 'INC-1041',
      title: 'Replace the tripped 32A three-pole breaker on the ARB floor 2 panel',
      category: 'ELECTRICAL',
      priority: 'P1',
      status: 'BLOCKED',
      location: 'Aryabhata Block, floor 2 electrical room',
      asset: 'AST-DB-ARB-F2 floor 2 power panel',
      requiredSkills: [{ code: 'ELECTRICAL', minLevel: 2 }],
      assignedTechnicianId: 'T-01',
      assignedTechnicianName: 'Ravi Kumar',
      estimatedMinutes: 90,
      blockReason: 'WAITING_FOR_PARTS',
      parts: [{ sku: 'MCB-32A-3P', name: 'MCB 32A three pole', qty: 1, state: 'SHORT', available: 0 }],
      sla: sla(clock, 'AT_RISK', 78, 52),
      safetyNote: 'Isolate the floor 2 supply at the main board before opening the panel. Two people for this job.',
      needsReassignment: null,
      approvalId: 'APR-610',
      createdAt: at(-55),
    }),
    make({
      id: 'WO-213',
      incidentId: 'INC-1042',
      title: 'Re-power the floor 2 switch and verify the three access points',
      category: 'NETWORK',
      priority: 'P1',
      status: 'ASSIGNED',
      location: 'Aryabhata Block, floor 2 network cabinet',
      asset: 'AST-SW-ARB-F2 floor 2 switch',
      requiredSkills: [{ code: 'NETWORK', minLevel: 2 }],
      assignedTechnicianId: 'T-03',
      assignedTechnicianName: 'Joseph Paul',
      estimatedMinutes: 45,
      blockReason: null,
      parts: [],
      sla: sla(clock, 'AT_RISK', 91, 21),
      safetyNote: null,
      needsReassignment: null,
      approvalId: null,
      createdAt: at(-27),
    }),
    make({
      id: 'WO-216',
      incidentId: 'INC-1041',
      title: 'Replace tube lights in the Administration block, room ADM-102',
      category: 'ELECTRICAL',
      priority: 'P3',
      status: 'ASSIGNED',
      location: 'Administration and Seminar Hall, room ADM-102',
      asset: null,
      requiredSkills: [{ code: 'ELECTRICAL', minLevel: 1 }],
      assignedTechnicianId: 'T-01',
      assignedTechnicianName: 'Ravi Kumar',
      estimatedMinutes: 30,
      blockReason: null,
      parts: [{ sku: 'LED-TUBE-18W', name: 'LED tube light 18W', qty: 4, state: 'RESERVED', available: 15 }],
      sla: sla(clock, 'ON_TRACK', 14, 350),
      safetyNote: null,
      needsReassignment: null,
      approvalId: null,
      createdAt: at(-20),
    }),
    make({
      id: 'WO-210',
      incidentId: 'INC-1036',
      title: 'Inspect and repair the projector in ARB-205',
      category: 'EQUIPMENT',
      priority: 'P2',
      status: 'ASSIGNED',
      location: 'Aryabhata Block, room ARB-205',
      asset: 'AST-PR-ARB-205 projector',
      requiredSkills: [{ code: 'GENERAL', minLevel: 2 }],
      assignedTechnicianId: 'T-04',
      assignedTechnicianName: 'Lakshmi Bose',
      estimatedMinutes: 60,
      blockReason: null,
      parts: [{ sku: 'HDMI-5M', name: 'HDMI cable 5m', qty: 1, state: 'RESERVED', available: 10 }],
      sla: sla(clock, 'ON_TRACK', 41, 140),
      safetyNote: null,
      needsReassignment: { reason: 'Lakshmi Bose marked herself sick at 08:50', suggestedTechnicianId: 'T-06', suggestedName: 'Sneha Joshi' },
      approvalId: null,
      createdAt: at(-120),
    }),
    make({
      id: 'WO-209',
      incidentId: 'INC-1038',
      title: 'Fix the leaking tap in KLH-304',
      category: 'PLUMBING',
      priority: 'P3',
      status: 'IN_PROGRESS',
      location: 'Kalam Hostel, room KLH-304',
      asset: null,
      requiredSkills: [{ code: 'PLUMBING', minLevel: 2 }],
      assignedTechnicianId: 'T-05',
      assignedTechnicianName: 'Hari Menon',
      estimatedMinutes: 60,
      blockReason: null,
      parts: [{ sku: 'TAP-15MM', name: 'Tap 15mm', qty: 1, state: 'ISSUED', available: 8 }],
      sla: sla(clock, 'ON_TRACK', 34, 190),
      safetyNote: null,
      needsReassignment: null,
      approvalId: null,
      createdAt: at(-280),
    }),
    make({
      id: 'WO-214',
      incidentId: 'INC-1034',
      title: 'Diagnose the air conditioner in lab RLB-102',
      category: 'HVAC',
      priority: 'P3',
      status: 'PENDING_ASSIGNMENT',
      location: 'Raman Research Labs, room RLB-102',
      asset: 'AST-AC-RLB-102 air conditioner',
      requiredSkills: [{ code: 'HVAC', minLevel: 2 }],
      assignedTechnicianId: null,
      assignedTechnicianName: null,
      estimatedMinutes: 120,
      blockReason: null,
      parts: [],
      sla: sla(clock, 'ON_TRACK', 12, 400),
      safetyNote: null,
      needsReassignment: null,
      approvalId: null,
      createdAt: at(-58),
    }),
    make({
      id: 'WO-205',
      incidentId: 'INC-1027',
      title: 'Replace the door hinge in BHB-105',
      category: 'CARPENTRY',
      priority: 'P4',
      status: 'COMPLETED',
      location: 'Bhaskara Block, room BHB-105',
      asset: null,
      requiredSkills: [{ code: 'CARPENTRY', minLevel: 1 }],
      assignedTechnicianId: 'T-05',
      assignedTechnicianName: 'Hari Menon',
      estimatedMinutes: 30,
      blockReason: null,
      parts: [{ sku: 'HINGE-4IN', name: 'Door hinge 4 inch', qty: 2, state: 'ISSUED', available: 18 }],
      sla: sla(clock, 'MET', 60, 0),
      safetyNote: null,
      needsReassignment: null,
      approvalId: null,
      createdAt: at(-1480),
    }),
  ]
}

const SHIFT = (start: number) => `${String(start).padStart(2, '0')}:00 to ${String(start + 8).padStart(2, '0')}:00`

export function buildTechnicians(): TechnicianCard[] {
  const state: Record<string, Pick<TechnicianCard, 'availability' | 'openTasks' | 'currentTask'>> = {
    'T-01': { availability: 'BUSY', openTasks: 2, currentTask: 'WO-212 blocked on a part' },
    'T-02': { availability: 'AVAILABLE', openTasks: 0, currentTask: null },
    'T-03': { availability: 'BUSY', openTasks: 1, currentTask: 'WO-213 floor 2 switch' },
    'T-04': { availability: 'SICK', openTasks: 1, currentTask: 'WO-210 needs reassignment' },
    'T-05': { availability: 'BUSY', openTasks: 1, currentTask: 'WO-209 leaking tap' },
    'T-06': { availability: 'AVAILABLE', openTasks: 0, currentTask: null },
  }
  const shiftStart: Record<string, number> = { 'T-01': 8, 'T-02': 8, 'T-03': 8, 'T-04': 12, 'T-05': 8, 'T-06': 12 }
  return campus.technicians.map((tech) => {
    const info = state[tech.id] ?? { availability: 'AVAILABLE' as const, openTasks: 0, currentTask: null }
    return {
      id: tech.id,
      name: tech.name,
      department: departmentName(tech.departmentId),
      skills: tech.skills,
      availability: info.availability,
      shift: SHIFT(shiftStart[tech.id] ?? 8),
      openTasks: info.openTasks,
      maxTasks: tech.maxConcurrentTasks,
      workloadPercent: Math.round((info.openTasks / tech.maxConcurrentTasks) * 100),
      currentTask: info.currentTask,
    }
  })
}

export function buildTodaySessions(): TodaySession[] {
  return [
    { id: 'ts1', course: 'Operating Systems end semester', room: 'ARB-204', start: '09:00', end: '12:00', group: 'CSE-3A', headcount: 58, kind: 'EXAM', status: 'AFFECTED', note: 'Room has no power (INC-1041). You invigilate.', alternative: { roomCode: 'ARB-105', note: 'Free all morning, seats 60' } },
    { id: 'ts2', course: 'Operating Systems', room: 'ARB-205', start: '13:30', end: '14:30', group: 'CSE-3B', headcount: 56, kind: 'LECTURE', status: 'AFFECTED', note: 'Floor 2 has no power. The repair is waiting for a part.', alternative: { roomCode: 'ARB-103', note: 'Free, seats 60' } },
    { id: 'ts3', course: 'Database Systems', room: 'ARB-104', start: '14:30', end: '15:30', group: 'CSE-2A', headcount: 57, kind: 'LECTURE', status: 'NORMAL', note: null, alternative: null },
    { id: 'ts4', course: 'Office hours', room: 'ARB-306', start: '15:45', end: '16:45', group: 'Open', headcount: 0, kind: 'LECTURE', status: 'NORMAL', note: null, alternative: null },
  ]
}

export function buildBookings(clock: Clock): BookingRow[] {
  const { at } = clock
  const day = (days: number, hour: number) => {
    const date = new Date(clock.now + days * 86_400_000)
    date.setHours(hour, 0, 0, 0)
    return date.toISOString()
  }
  void at
  return [
    { id: 'BK-2201', roomCode: 'ARB-301', roomType: 'CLASSROOM', building: 'Aryabhata Block', purpose: 'Extra class: Operating Systems revision', start: day(0, 16), end: day(0, 18), status: 'CONFIRMED', requester: 'Dr. Kiran Rao', headcount: 45, impact: 'LECTURE' },
    { id: 'BK-2196', roomCode: 'ADM-101', roomType: 'SEMINAR', building: 'Administration and Seminar Hall', purpose: 'Guest lecture on distributed systems', start: day(2, 14), end: day(2, 16), status: 'CONFIRMED', requester: 'Dr. Kiran Rao', headcount: 150, impact: 'EVENT' },
    { id: 'BK-2188', roomCode: 'RLB-201', roomType: 'LAB', building: 'Raman Research Labs', purpose: 'Project demo, CSE-4A', start: day(3, 10), end: day(3, 12), status: 'REQUESTED', requester: 'Dr. Kiran Rao', headcount: 28, impact: 'PRACTICAL' },
    { id: 'BK-2150', roomCode: 'ARB-204', roomType: 'CLASSROOM', building: 'Aryabhata Block', purpose: 'Tutorial', start: day(-4, 11), end: day(-4, 12), status: 'RESCHEDULED', requester: 'Dr. Kiran Rao', headcount: 40, impact: 'LECTURE' },
    { id: 'BK-2210', roomCode: 'BHB-203', roomType: 'CLASSROOM', building: 'Bhaskara Block', purpose: 'ECE department review', start: day(1, 15), end: day(1, 16), status: 'CONFIRMED', requester: 'Vikram Shetty', headcount: 30, impact: null },
  ]
}

export function buildSlaRows(): SlaRow[] {
  return [
    { id: 'SLA-1', subject: 'INC-1042 Wi-Fi down across Aryabhata Block', subjectId: 'INC-1042', priority: 'P1', category: 'NETWORK', state: 'AT_RISK', percentElapsed: 91, remaining: '21 min left', owner: 'Joseph Paul', escalationLevel: 1, risk: { probability: 0.82, factor: 'Waiting on INC-1041 power restore' } },
    { id: 'SLA-2', subject: 'INC-1041 Power lost on Aryabhata floor 2', subjectId: 'INC-1041', priority: 'P1', category: 'ELECTRICAL', state: 'AT_RISK', percentElapsed: 78, remaining: '52 min left', owner: 'Ravi Kumar', escalationLevel: 0, risk: { probability: 0.74, factor: 'Part out of stock, no ETA' } },
    { id: 'SLA-3', subject: 'WO-210 Projector ARB-205', subjectId: 'WO-210', priority: 'P2', category: 'EQUIPMENT', state: 'ON_TRACK', percentElapsed: 41, remaining: '2 h 20 min left', owner: 'Lakshmi Bose', escalationLevel: 0, risk: { probability: 0.38, factor: 'Technician unavailable, needs reassignment' } },
    { id: 'SLA-4', subject: 'INC-1038 Leaking tap KLH-304', subjectId: 'INC-1038', priority: 'P3', category: 'PLUMBING', state: 'ON_TRACK', percentElapsed: 34, remaining: '3 h 10 min left', owner: 'Hari Menon', escalationLevel: 0, risk: null },
    { id: 'SLA-5', subject: 'INC-1034 Air conditioner RLB-102', subjectId: 'INC-1034', priority: 'P3', category: 'HVAC', state: 'ON_TRACK', percentElapsed: 12, remaining: '6 h 40 min left', owner: null, escalationLevel: 0, risk: null },
    { id: 'SLA-6', subject: 'INC-1031 Burning smell near cafeteria', subjectId: 'INC-1031', priority: 'P2', category: 'SAFETY', state: 'PAUSED', percentElapsed: 20, remaining: 'Paused awaiting reporter reply', owner: null, escalationLevel: 0, risk: null },
    { id: 'SLA-7', subject: 'INC-1019 Switch failure BHB floor 1', subjectId: 'INC-1019', priority: 'P2', category: 'NETWORK', state: 'BREACHED', percentElapsed: 118, remaining: 'overdue by 22 min', owner: 'Joseph Paul', escalationLevel: 2, risk: null },
  ]
}

export function buildAnalytics(): AnalyticsOverview {
  return {
    open: {
      total: 11,
      byStatus: [
        { label: 'Acknowledged', value: 3 },
        { label: 'Assigned', value: 2 },
        { label: 'In progress', value: 3 },
        { label: 'Needs clarification', value: 1 },
        { label: 'Waiting for parts', value: 2 },
      ],
      byCategory: [
        { label: 'Electrical', value: 4 },
        { label: 'Network', value: 3 },
        { label: 'Plumbing', value: 1 },
        { label: 'Equipment', value: 2 },
        { label: 'HVAC', value: 1 },
      ],
    },
    sla: {
      rate: 87,
      trend: [92, 90, 94, 89, 86, 91, 87],
      byPriority: [
        { label: 'P1 critical', value: 71 },
        { label: 'P2 high', value: 84 },
        { label: 'P3 medium', value: 93 },
        { label: 'P4 low', value: 98 },
      ],
    },
    utilisation: {
      rooms: [
        { label: 'Aryabhata Block', value: 78 },
        { label: 'Bhaskara Block', value: 71 },
        { label: 'Ramanujan Block', value: 64 },
        { label: 'Raman Research Labs', value: 83 },
        { label: 'Administration and Seminar Hall', value: 41 },
      ],
      technicians: [
        { label: 'Ravi Kumar', value: 82 },
        { label: 'Joseph Paul', value: 74 },
        { label: 'Hari Menon', value: 61 },
        { label: 'Meena Das', value: 22 },
        { label: 'Sneha Joshi', value: 18 },
      ],
    },
    shortages: [
      { name: 'MCB 32A three pole', onHand: 0, threshold: 4, blocked: 1 },
      { name: 'UPS 1kVA', onHand: 0, threshold: 1, blocked: 0 },
      { name: 'Projector 4000 lumen', onHand: 0, threshold: 1, blocked: 0 },
      { name: 'AC fan motor', onHand: 0, threshold: 2, blocked: 0 },
    ],
    recurring: [
      { name: 'Access point ARB floor 2 #2', location: 'ARB-203', count: 6, last: '9 days ago' },
      { name: 'Projector', location: 'ARB-204', count: 4, last: '3 weeks ago' },
      { name: 'Bathroom tap', location: 'KLH-304', count: 4, last: 'Today' },
      { name: 'Power panel BHB floor 1', location: 'BHB-103', count: 3, last: '6 weeks ago' },
    ],
    daily: [
      { label: 'Thu', value: 7 },
      { label: 'Fri', value: 9 },
      { label: 'Sat', value: 3 },
      { label: 'Sun', value: 2 },
      { label: 'Mon', value: 11 },
      { label: 'Tue', value: 8 },
      { label: 'Wed', value: 24 },
    ],
  }
}
