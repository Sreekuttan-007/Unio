/**
 * INTERIM types for endpoints the backend adds in later phases.
 *
 * The prototype screens call these endpoints now, served by src/mocks, so the interface can be
 * designed before the backend exists. As each phase lands, `python -m tools.contract` and
 * `npm run gen:api` generate the real type, and the matching interface here is deleted in favour
 * of an alias in platform/api/types.ts. The field names are the contract the backend will follow.
 */
import type { SlaState } from '@/ui'

export type Priority = 'P1' | 'P2' | 'P3' | 'P4'
export type Category = 'ELECTRICAL' | 'NETWORK' | 'PLUMBING' | 'HVAC' | 'CARPENTRY' | 'EQUIPMENT' | 'HOUSEKEEPING' | 'SAFETY' | 'OTHER'
export type IncidentStatus =
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'NEEDS_CLARIFICATION'
  | 'ACKNOWLEDGED'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED'

export interface ActionHint {
  key: string
  label: string
}

export interface UnavailableHint extends ActionHint {
  reason: string
}

export interface Sla {
  state: SlaState
  percentElapsed: number
  /** Already worded for people, such as "52 min left" or "overdue by 10 min". */
  remaining: string
  dueAt: string
}

export interface TimelineItem {
  id: string
  title: string
  detail?: string
  at: string
  tone?: 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'
}

export interface Incident {
  id: string
  title: string
  category: Category
  priority: Priority
  status: IncidentStatus
  buildingId: string
  buildingName: string
  regionId: string
  roomCodes: string[]
  reportCount: number
  channels: { FORM: number; CHAT: number; EMAIL: number }
  summary: { text: string; source: 'AI' | 'TEMPLATE'; basedOnReportCount: number }
  impact: { rooms: number; sessions: number; exams: number; people: number }
  sla: Sla
  assignedTo: string | null
  relatedIds: string[]
  createdAt: string
  updatedAt: string
  timeline: TimelineItem[]
  availableActions: ActionHint[]
  unavailableActions: UnavailableHint[]
}

export interface ReportSummary {
  id: string
  incidentId: string
  title: string
  status: IncidentStatus
  priority: Priority
  channel: 'FORM' | 'CHAT' | 'EMAIL'
  submittedAt: string
  /** True when the report joined an incident that already existed. */
  joinedExisting: boolean
  incidentReportCount: number
  summary: string
  timeline: TimelineItem[]
  canGiveFeedback: boolean
}

export interface Extraction {
  category: Category
  categoryConfidence: number
  urgency: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  location: { text: string; roomCode: string | null; buildingName: string | null }
  asset: string | null
  /** Set when something essential is missing. The wizard asks it instead of guessing. */
  clarification: string | null
  duplicate: { incidentId: string; title: string; reportCount: number } | null
  source: 'AI' | 'RULE'
}

export interface InboundEmail {
  id: string
  from: string
  subject: string
  body: string
  receivedAt: string
  status: 'PENDING' | 'CONVERTED' | 'CLARIFICATION_SENT' | 'DUPLICATE_IGNORED'
  extraction: { category: Category; location: string; urgency: string; asset: string | null; confidence: number } | null
  incidentId: string | null
  note: string | null
}

export type WorkOrderStatus = 'PENDING_ASSIGNMENT' | 'ASSIGNED' | 'ACCEPTED' | 'IN_PROGRESS' | 'BLOCKED' | 'COMPLETED' | 'VERIFIED'

export interface PartLine {
  sku: string
  name: string
  qty: number
  state: 'RESERVED' | 'SHORT' | 'ISSUED'
  available: number
}

export interface WorkOrder {
  id: string
  incidentId: string
  title: string
  category: Category
  priority: Priority
  status: WorkOrderStatus
  location: string
  asset: string | null
  requiredSkills: { code: string; minLevel: number }[]
  assignedTechnicianId: string | null
  assignedTechnicianName: string | null
  estimatedMinutes: number
  blockReason: 'WAITING_FOR_PARTS' | 'ACCESS' | 'SKILL_MISMATCH' | null
  parts: PartLine[]
  sla: Sla
  safetyNote: string | null
  needsReassignment: { reason: string; suggestedTechnicianId: string; suggestedName: string } | null
  approvalId: string | null
  createdAt: string
  availableActions: ActionHint[]
  unavailableActions: UnavailableHint[]
}

export interface TechnicianCard {
  id: string
  name: string
  department: string
  skills: { code: string; level: number }[]
  availability: 'AVAILABLE' | 'BUSY' | 'ON_LEAVE' | 'SICK' | 'OFF_SHIFT'
  shift: string
  openTasks: number
  maxTasks: number
  workloadPercent: number
  currentTask: string | null
}

export interface Finding {
  code: string
  /** HARD cannot be overridden. APPROVAL needs an approved override. SOFT needs a reason. */
  severity: 'HARD' | 'SOFT' | 'APPROVAL'
  message: string
  affected: string
}

export interface Candidate {
  technicianId: string
  name: string
  score: number
  factors: { label: string; value: string; good: boolean }[]
  decision: 'ALLOW' | 'WARN' | 'BLOCK'
  findings: Finding[]
}

export interface CollisionRecord {
  id: string
  at: string
  actionType: string
  summary: string
  actor: string
  decision: 'ALLOW' | 'WARN' | 'REQUIRE_APPROVAL' | 'BLOCK'
  findings: Finding[]
  override: { by: string; reason: string } | null
}

export interface ImpactSession {
  id: string
  course: string
  group: string
  room: string
  start: string
  end: string
  kind: 'LECTURE' | 'PRACTICAL' | 'EXAM'
  headcount: number
  alternative: { roomCode: string; note: string } | null
}

export interface ImpactReport {
  incidentId: string
  chain: { id: string; depth: number; kind: string; title: string; detail?: string; severity?: 'HIGH' | 'MEDIUM' | 'LOW'; reason?: string }[]
  totals: { rooms: number; sessions: number; exams: number; people: number; workOrders: number }
  affectedSessions: ImpactSession[]
  affectedRegionIds: string[]
}

export interface Plan {
  id: string
  title: string
  summary: string
  feasible: boolean
  metrics: { label: string; value: string }[]
  findings: { severity: 'HARD' | 'SOFT'; message: string }[]
  actions: string[]
}

export interface SimulationRun {
  id: string
  incidentId: string
  snapshotAt: string
  plans: Plan[]
  recommendedPlanId: string | null
}

export interface BookingRow {
  id: string
  roomCode: string
  roomType: string
  building: string
  purpose: string
  start: string
  end: string
  status: 'CONFIRMED' | 'REQUESTED' | 'RESCHEDULED' | 'CANCELLED' | 'REJECTED'
  requester: string
  headcount: number
  impact: 'LECTURE' | 'PRACTICAL' | 'EXAM' | 'EVENT' | null
  rescheduledCount?: number
  availableActions?: ActionHint[]
  unavailableActions?: UnavailableHint[]
}

export interface BookingCheck {
  allowed: boolean
  decision?: 'ALLOW' | 'WARN' | 'REQUIRE_APPROVAL' | 'BLOCK'
  findings: Finding[]
  alternatives: { roomCode: string; type: string; capacity: number; building: string; fit: string }[]
  timeAlternatives?: { label: string; start: string; end: string; reason: string }[]
  affectedClasses: { course: string; group: string; headcount: number; start: string; end: string; kind?: 'SESSION' | 'BOOKING' }[]
  /** True when the only findings are warnings, which go ahead with a written reason. */
  requiresReason?: boolean
  requiresApproval?: boolean
  stateToken?: string
}

export interface TodaySession {
  id: string
  course: string
  room: string
  start: string
  end: string
  group: string
  headcount: number
  kind: 'LECTURE' | 'PRACTICAL' | 'EXAM'
  status: 'NORMAL' | 'AFFECTED'
  note: string | null
  alternative: { roomCode: string; note: string } | null
}

export interface StockRow {
  id: string
  sku: string
  name: string
  category: string
  unit: string
  onHand: number
  reserved: number
  available: number
  threshold: number
  critical: boolean
  location: string
  status: 'OK' | 'LOW' | 'OUT'
  blockedWorkOrders: number
}

export interface Approval {
  id: string
  type: 'PURCHASE' | 'COSTLY_REPAIR' | 'OVERRIDE'
  status: 'SUBMITTED' | 'UNDER_REVIEW' | 'NEEDS_CLARIFICATION' | 'APPROVED' | 'REJECTED' | 'EXECUTED' | 'STALE'
  title: string
  requesterName: string
  requesterRole: string
  amountPaise: number
  justification: string
  linkedWorkOrderId: string | null
  linkedIncidentId: string | null
  lines: { name: string; qty: number; estimatePaise: number }[]
  evidence: { label: string; value: string; tone?: 'neutral' | 'warning' | 'danger' | 'success' }[]
  routing: string
  decisions: { by: string; decision: string; reason: string | null; at: string }[]
  createdAt: string
  availableActions: ActionHint[]
  unavailableActions: UnavailableHint[]
}

export interface PurchaseOrder {
  id: string
  approvalId: string
  supplier: string
  totalPaise: number
  status: 'ORDERED' | 'PARTIALLY_RECEIVED' | 'RECEIVED'
  orderedAt: string
  lines: { sku: string; name: string; qty: number; unitPaise: number; received: number }[]
}

export interface InvoiceLine {
  lineNo: number
  description: string
  qty: number
  unitPaise: number
  poQty: number | null
  poUnitPaise: number | null
  match: 'OK' | 'QTY' | 'PRICE' | 'EXTRA'
  confidence: number
}

export interface Invoice {
  id: string
  supplier: string
  invoiceNumber: string
  invoiceDate: string
  purchaseOrderId: string
  status: 'EXTRACTED' | 'DISCREPANCY' | 'MATCHED' | 'VALIDATED' | 'POSTED'
  totalPaise: number
  fileName: string
  lines: InvoiceLine[]
  discrepancies: { code: string; message: string; resolved: boolean }[]
  extractionSource: 'AI' | 'MANUAL'
}

export interface GoodsReceipt {
  id: string
  purchaseOrderId: string
  invoiceId: string | null
  status: 'PENDING' | 'VALIDATED'
  lines: { name: string; ordered: number; received: number }[]
  receivedAt: string
}

export interface SlaRow {
  id: string
  subject: string
  subjectId: string
  priority: Priority
  category: Category
  state: SlaState
  percentElapsed: number
  remaining: string
  owner: string | null
  escalationLevel: number
  risk: { probability: number; factor: string } | null
}

export interface Notice {
  id: string
  title: string
  body: string
  severity: 'INFO' | 'WARNING' | 'CRITICAL'
  audience: string
  at: string
}

export interface AnalyticsOverview {
  open: { total: number; byStatus: { label: string; value: number }[]; byCategory: { label: string; value: number }[] }
  sla: { rate: number; trend: number[]; byPriority: { label: string; value: number }[] }
  utilisation: { rooms: { label: string; value: number }[]; technicians: { label: string; value: number }[] }
  shortages: { name: string; onHand: number; threshold: number; blocked: number }[]
  recurring: { name: string; location: string; count: number; last: string }[]
  daily: { label: string; value: number }[]
}

export interface CollisionRule {
  id: string
  name: string
  description: string
  actionTypes: string[]
  severity: 'HARD' | 'SOFT'
  enabled: boolean
  locked: boolean
  parameter: string | null
}

export interface SlaPolicy {
  id: string
  category: Category
  priority: Priority
  responseMinutes: number
  resolutionMinutes: number
  escalations: { level: number; atPercent: number; notify: string }[]
}

export interface IntegrationState {
  ai: { provider: string; model: string; features: { key: string; label: string; enabled: boolean; mode: 'AI' | 'RULES' }[] }
  email: { address: string; polling: string; lastPoll: string; processed: number }
  webhooks: { id: string; url: string; events: string[]; enabled: boolean; lastStatus: number; lastAt: string }[]
  channels: { key: string; label: string; enabled: boolean }[]
}

export interface SystemHealth {
  api: { status: 'UP' | 'DOWN'; latencyMs: number }
  database: { status: 'UP' | 'DOWN'; collections: number; documents: number }
  ai: { status: 'UP' | 'DEGRADED' | 'OFF'; note: string }
  jobs: { name: string; lastRun: string; status: 'OK' | 'LATE' }[]
  dataQuality: { label: string; ok: boolean; detail: string }[]
}

export interface ScenarioInfo {
  id: string
  title: string
  description: string
  covers: string[]
}
