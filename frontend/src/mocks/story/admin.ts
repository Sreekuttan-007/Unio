import type { CollisionRule, IntegrationState, ScenarioInfo, SlaPolicy, SystemHealth } from '@/types/domain'
import type { Clock } from './helpers'

export function buildRules(): CollisionRule[] {
  return [
    { id: 'ROOM-001', name: 'Room overlap', description: 'A room cannot hold two bookings or sessions at once.', actionTypes: ['CREATE_BOOKING', 'RESCHEDULE'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'ROOM-002', name: 'Room closed or under maintenance', description: 'A closed room cannot be booked.', actionTypes: ['CREATE_BOOKING'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'ROOM-003', name: 'Room capacity', description: 'Headcount must fit the room.', actionTypes: ['CREATE_BOOKING'], severity: 'HARD', enabled: true, locked: false, parameter: null },
    { id: 'ROOM-004', name: 'Room type', description: 'A practical belongs in a lab, not a classroom.', actionTypes: ['CREATE_BOOKING'], severity: 'SOFT', enabled: true, locked: false, parameter: null },
    { id: 'TECH-001', name: 'Technician skill', description: 'The technician must hold every required skill at the required level.', actionTypes: ['ASSIGN_TECHNICIAN'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'TECH-002', name: 'Technician overlap', description: 'A technician cannot be in two places at once.', actionTypes: ['ASSIGN_TECHNICIAN'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'TECH-003', name: 'Technician workload', description: 'Warn above this many concurrent tasks.', actionTypes: ['ASSIGN_TECHNICIAN'], severity: 'SOFT', enabled: true, locked: false, parameter: '3 tasks' },
    { id: 'TECH-004', name: 'Technician shift', description: 'Warn when the work falls outside the shift.', actionTypes: ['ASSIGN_TECHNICIAN'], severity: 'SOFT', enabled: true, locked: false, parameter: null },
    { id: 'STOCK-001', name: 'Stock available', description: 'A part cannot be reserved beyond what is on hand and unreserved.', actionTypes: ['RESERVE_PART'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'APPR-001', name: 'No self-approval', description: 'The requester can never decide their own request.', actionTypes: ['APPROVE'], severity: 'HARD', enabled: true, locked: true, parameter: null },
    { id: 'APPR-002', name: 'Approval limit', description: 'Amounts above a role limit are routed to the next level.', actionTypes: ['APPROVE'], severity: 'HARD', enabled: true, locked: false, parameter: '₹25,000 Department Manager' },
    { id: 'STATE-001', name: 'Stale state', description: 'A plan is re-checked against live data just before it runs.', actionTypes: ['EXECUTE_PLAN'], severity: 'HARD', enabled: true, locked: true, parameter: null },
  ]
}

export function buildSlaPolicies(): SlaPolicy[] {
  const ladder = [
    { level: 1, atPercent: 75, notify: 'Department Manager' },
    { level: 2, atPercent: 100, notify: 'Facilities Administrator' },
  ]
  return [
    { id: 'SLA-NET-P1', category: 'NETWORK', priority: 'P1', responseMinutes: 15, resolutionMinutes: 240, escalations: ladder },
    { id: 'SLA-ELE-P1', category: 'ELECTRICAL', priority: 'P1', responseMinutes: 10, resolutionMinutes: 180, escalations: ladder },
    { id: 'SLA-EQP-P2', category: 'EQUIPMENT', priority: 'P2', responseMinutes: 60, resolutionMinutes: 480, escalations: ladder },
    { id: 'SLA-PLU-P3', category: 'PLUMBING', priority: 'P3', responseMinutes: 120, resolutionMinutes: 720, escalations: [ladder[1]!] },
    { id: 'SLA-HVA-P3', category: 'HVAC', priority: 'P3', responseMinutes: 120, resolutionMinutes: 1440, escalations: [ladder[1]!] },
  ]
}

export function buildIntegrations(clock: Clock): IntegrationState {
  return {
    ai: {
      provider: 'Gemini',
      model: 'gemini-3.8-flash',
      features: [
        { key: 'mlTriage', label: 'Categorise and prioritise reports', enabled: true, mode: 'AI' },
        { key: 'mlDuplicate', label: 'Detect duplicate and related reports', enabled: true, mode: 'AI' },
        { key: 'mlSummary', label: 'Write incident summaries', enabled: true, mode: 'AI' },
        { key: 'ocr', label: 'Read invoices', enabled: true, mode: 'AI' },
        { key: 'slaRisk', label: 'Warn early about SLA risk', enabled: true, mode: 'AI' },
      ],
    },
    email: { address: 'help@aurora.example (simulated)', polling: 'Every 30 seconds', lastPoll: clock.at(-1), processed: 142 },
    webhooks: [
      { id: 'WH-1', url: 'https://facilities-chat.example/hooks/unio', events: ['incident.created', 'sla.breached'], enabled: true, lastStatus: 200, lastAt: clock.at(-4) },
      { id: 'WH-2', url: 'https://erp.example/hooks/procurement', events: ['approval.approved', 'receipt.validated'], enabled: true, lastStatus: 200, lastAt: clock.at(-90) },
    ],
    channels: [
      { key: 'in_app', label: 'In-app notifications', enabled: true },
      { key: 'email', label: 'Email (simulated inbox)', enabled: true },
      { key: 'push', label: 'Push to the phone app', enabled: false },
    ],
  }
}

export function buildHealth(clock: Clock): SystemHealth {
  return {
    api: { status: 'UP', latencyMs: 42 },
    database: { status: 'UP', collections: 31, documents: 2845 },
    ai: { status: 'UP', note: 'Gemini answering in about 1.4 seconds' },
    jobs: [
      { name: 'SLA sweep', lastRun: clock.at(-1), status: 'OK' },
      { name: 'Email inbox poll', lastRun: clock.at(-1), status: 'OK' },
      { name: 'Outbox dispatcher', lastRun: clock.at(0), status: 'OK' },
    ],
    dataQuality: [
      { label: 'Every room has a map region', ok: true, detail: '105 of 105 rooms bound' },
      { label: 'No dangling dependency edges', ok: true, detail: '341 edges checked' },
      { label: 'No double-booked rooms in the timetable', ok: true, detail: '382 sessions checked' },
      { label: 'Technicians have current shifts', ok: true, detail: '6 of 6 technicians' },
      { label: 'Critical parts above reorder level', ok: false, detail: 'MCB 32A three pole is out of stock' },
    ],
  }
}

export function buildScenarios(): ScenarioInfo[] {
  return [
    { id: 'A', title: 'Scenario A: exam room lost', description: 'A power fault closes the room of a morning exam. Bookings collide, the simulator compares recovery plans, and only the affected people are told.', covers: ['M5', 'Cascading impact', 'Simulator'] },
    { id: 'B', title: 'Scenario B: Wi-Fi outage', description: 'Fourteen reports arrive by form, chat and email. They merge into one incident with a summary, and a replayed webhook changes nothing.', covers: ['M1', 'M2', 'C4', 'C5'] },
    { id: 'C', title: 'Scenario C: critical part out of stock', description: 'A technician flags a missing part, work is blocked, a purchase is approved by someone other than the requester, and an invoice is checked before stock is posted once.', covers: ['M6', 'M7', 'Invoice to inventory'] },
    { id: 'D', title: 'Scenario D: technician unavailable', description: 'A technician marks themselves sick. Their work is flagged, an unqualified replacement is refused, and a qualified one is proposed.', covers: ['M4', 'Collision engine'] },
  ]
}
