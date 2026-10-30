import { delay, http, HttpResponse } from 'msw'
import { API_ORIGIN, API_PREFIX } from '@/platform/api/config'
import type {
  Approval,
  BookingCheck,
  BookingRow,
  Candidate,
  Extraction,
  Finding,
  Incident,
  InboundEmail,
  Invoice,
  ReportSummary,
  TechnicianCard,
  WorkOrder,
} from '@/types/domain'
import type { RegionOverlay } from '@/ui'
import { buildHealth, buildIntegrations, buildRules, buildScenarios, buildSlaPolicies } from './story/admin'
import { buildStock, buildApprovals, buildInvoices, buildPurchaseOrders, buildReceipts } from './story/procurement'
import { buildBookings, buildAnalytics, buildSlaRows, buildTechnicians, buildTodaySessions, buildWorkOrders, actionsFor } from './story/operations'
import { buildCollisions, buildEmails, buildImpact, buildIncidents, buildNotices, buildReports, buildSimulation } from './story/incidents'
import { buildingById, campus, departmentName, regionCentre, roomByCode } from './story/campus'
import { makeClock } from './story/helpers'

/**
 * Prototype endpoints. They use the paths and field names the real backend will adopt in later
 * phases, so a screen written against them keeps working once the mock is switched off.
 *
 * These are NOT an authority. They fake enough rules (conflicts, self-approval, stale plans, repeat-safe
 * stock posting) to make the screens feel real. The real rules live in the backend.
 */

const BASE = `${API_ORIGIN}${API_PREFIX}`
const lag = () => delay(import.meta.env.MODE === 'test' ? 0 : 220)

const USER_NAME: Record<string, string> = {
  STUDENT: 'Asha Nair',
  FACULTY: 'Dr. Kiran Rao',
  DEPARTMENT_MANAGER: 'Meera Iyer',
  FACILITIES_ADMIN: 'Arjun Menon',
  PROCUREMENT_APPROVER: 'Divya Pillai',
  TECHNICIAN: 'Ravi Kumar',
  SYSTEM_ADMIN: 'Sam Thomas',
}

const roleOf = (request: Request): string | null => request.headers.get('authorization')?.replace('Bearer mock.', '') ?? null

const problem = (status: number, code: string, message: string, details: Record<string, unknown> = {}) =>
  HttpResponse.json({ code, message, details, correlationId: 'mock-correlation' }, { status })

const unauthenticated = () => problem(401, 'UNAUTHENTICATED', 'Please sign in to continue.')

function extract(text: string, incidents: Incident[]): Extraction {
  const lower = text.toLowerCase()
  const has = (...words: string[]) => words.some((word) => lower.includes(word))
  let category: Extraction['category'] = 'OTHER'
  let confidence = 0.42
  const rules: [Extraction['category'], string[]][] = [
    ['NETWORK', ['wifi', 'wi-fi', 'internet', 'network', 'lan ']],
    ['SAFETY', ['smoke', 'burning', 'fire', 'spark', 'gas smell']],
    ['ELECTRICAL', ['power', 'light', 'electric', 'socket', 'switch board', 'tripped', 'fan']],
    ['PLUMBING', ['leak', 'tap', 'water', 'drain', 'flush', 'toilet']],
    ['HVAC', ['air condition', ' ac ', 'cooling', 'ac is']],
    ['EQUIPMENT', ['projector', 'screen', 'hdmi', 'mic', 'speaker']],
    ['CARPENTRY', ['door', 'hinge', 'bench', 'desk', 'window', 'chair']],
  ]
  for (const [name, words] of rules) {
    if (has(...words)) {
      category = name
      confidence = 0.9
      break
    }
  }
  const match = /\b([a-z]{3})[\s-]?(\d{3})\b/i.exec(text)
  const roomCode = match ? `${match[1]!.toUpperCase()}-${match[2]}` : null
  const room = roomCode ? roomByCode(roomCode) : undefined
  const named = campus.buildings.find((b) => lower.includes(b.name.toLowerCase().split(' ')[0]!) || lower.includes(` ${b.code.toLowerCase()} `) || lower.endsWith(` ${b.code.toLowerCase()}`))
  const building = room ? buildingById(room.buildingId) : named
  const locationText = room ? `${room.code}, ${building?.name}` : building ? building.name : ''
  const urgency: Extraction['urgency'] = category === 'SAFETY' || has('spark', 'flood') ? 'CRITICAL' : has('exam', 'not working', 'no power', 'urgent', 'down') ? 'HIGH' : has('minor', 'whenever') ? 'LOW' : 'MEDIUM'
  const duplicateOf = building?.code === 'ARB' ? incidents.find((incident) => incident.category === category && incident.buildingId === 'B-ARB' && incident.status !== 'RESOLVED' && incident.status !== 'CLOSED') : undefined
  return {
    category,
    categoryConfidence: confidence,
    urgency,
    location: { text: locationText, roomCode: room?.code ?? null, buildingName: building?.name ?? null },
    asset: has('projector') ? 'Projector' : has('wifi', 'wi-fi') ? 'Wi-Fi access point' : has('tap') ? 'Tap' : has('ac ', 'air condition') ? 'Air conditioner' : null,
    clarification: building ? null : 'Which room or building is this in? Add a room code such as ARB-204.',
    duplicate: duplicateOf ? { incidentId: duplicateOf.id, title: duplicateOf.title, reportCount: duplicateOf.reportCount } : null,
    source: confidence > 0.5 ? 'AI' : 'RULE',
  }
}

function candidatesFor(order: WorkOrder, technicians: TechnicianCard[]): Candidate[] {
  return technicians
    .map((tech) => {
      const findings: Finding[] = []
      const factors: Candidate['factors'] = []
      const need = order.requiredSkills[0]
      const own = tech.skills.find((skill) => skill.code === need?.code)
      if (!own || own.level < (need?.minLevel ?? 0)) {
        findings.push({ code: 'TECH_SKILL', severity: 'HARD', message: `${tech.name} does not hold ${need?.code ?? 'the required skill'} at level ${need?.minLevel ?? 1}.`, affected: tech.id })
      }
      if (tech.availability === 'SICK' || tech.availability === 'ON_LEAVE') {
        findings.push({ code: 'TECH_UNAVAILABLE', severity: 'HARD', message: `${tech.name} is ${tech.availability === 'SICK' ? 'off sick' : 'on leave'} today.`, affected: tech.id })
      }
      if (tech.openTasks >= tech.maxTasks) {
        findings.push({ code: 'TECH_OVERLAP', severity: 'HARD', message: `${tech.name} already has ${tech.openTasks} of ${tech.maxTasks} tasks.`, affected: tech.id })
      } else if (tech.openTasks === tech.maxTasks - 1) {
        findings.push({ code: 'TECH_WORKLOAD', severity: 'SOFT', message: `${tech.name} would be at ${tech.openTasks + 1} of ${tech.maxTasks} tasks, with no spare capacity.`, affected: tech.id })
      }
      factors.push({ label: 'Skill', value: own ? `${need?.code} level ${own.level}` : 'No match', good: !!own && own.level >= (need?.minLevel ?? 0) })
      factors.push({ label: 'Workload', value: `${tech.openTasks} of ${tech.maxTasks} tasks`, good: tech.openTasks < tech.maxTasks - 1 })
      factors.push({ label: 'Shift', value: tech.shift, good: true })
      const hard = findings.some((finding) => finding.severity === 'HARD')
      const soft = findings.some((finding) => finding.severity === 'SOFT')
      const score = hard ? 0 : Math.round((own?.level ?? 0) * 18 + (100 - tech.workloadPercent) * 0.45 + (tech.department.startsWith('Electrical') ? 6 : 0))
      return { technicianId: tech.id, name: tech.name, score, factors, decision: hard ? ('BLOCK' as const) : soft ? ('WARN' as const) : ('ALLOW' as const), findings }
    })
    .sort((a, b) => b.score - a.score)
}

export function createDomainHandlers() {
  const clock = makeClock()
  const incidents = buildIncidents(clock)
  const workOrders = buildWorkOrders(clock)
  const technicians = buildTechnicians()
  const reports = buildReports(clock)
  const emails = buildEmails(clock)
  const collisions = buildCollisions(clock)
  const bookings = buildBookings(clock)
  const stock = buildStock()
  let approvals = buildApprovals(clock)
  const purchaseOrders = buildPurchaseOrders(clock)
  const invoices = buildInvoices()
  const receipts = buildReceipts(clock)
  const rules = buildRules()
  const integrations = buildIntegrations(clock)
  const executedPlans = new Set<string>()
  const postedReceipts = new Map<string, { sku: string; qty: number }[]>()
  let reportSequence = 5600
  let incidentSequence = 1043

  const approvalActions = (approval: Approval, role: string): Pick<Approval, 'availableActions' | 'unavailableActions'> => {
    const open = ['SUBMITTED', 'UNDER_REVIEW', 'NEEDS_CLARIFICATION'].includes(approval.status)
    if (!open) return { availableActions: [], unavailableActions: [] }
    if (approval.requesterName === USER_NAME[role]) {
      return {
        availableActions: [],
        unavailableActions: [{ key: 'approval.approve', label: 'Approve', reason: 'You raised this request, so someone else must decide it. Nobody approves their own request.' }],
      }
    }
    const deciders: Record<Approval['type'], string[]> = {
      PURCHASE: ['PROCUREMENT_APPROVER', 'FACILITIES_ADMIN'],
      COSTLY_REPAIR: ['PROCUREMENT_APPROVER', 'FACILITIES_ADMIN'],
      OVERRIDE: ['FACILITIES_ADMIN', 'DEPARTMENT_MANAGER'],
    }
    if (!deciders[approval.type].includes(role)) return { availableActions: [], unavailableActions: [] }
    if (role === 'DEPARTMENT_MANAGER' && approval.amountPaise > 2_500_000) {
      return { availableActions: [], unavailableActions: [{ key: 'approval.approve', label: 'Approve', reason: 'This is above your ₹25,000 limit, so it goes to Procurement.' }] }
    }
    return {
      availableActions: [
        { key: 'approval.approve', label: 'Approve' },
        { key: 'approval.reject', label: 'Reject' },
        { key: 'approval.clarify', label: 'Ask for clarification' },
      ],
      unavailableActions: [],
    }
  }

  const approvalsFor = (role: string) => {
    const visible = role === 'DEPARTMENT_MANAGER' ? approvals.filter((a) => a.requesterName === 'Meera Iyer') : approvals
    return visible.map((approval) => ({ ...approval, ...approvalActions(approval, role) }))
  }

  const incidentsFor = (role: string) => (role === 'DEPARTMENT_MANAGER' ? incidents.filter((incident) => incident.buildingId === 'B-ARB') : incidents)

  const workOrdersFor = (role: string) => {
    if (role === 'TECHNICIAN') return workOrders.filter((order) => order.assignedTechnicianId === 'T-01')
    if (role === 'DEPARTMENT_MANAGER') {
      const ids = new Set(incidents.filter((incident) => incident.buildingId === 'B-ARB').map((incident) => incident.id))
      return workOrders.filter((order) => ids.has(order.incidentId))
    }
    return workOrders
  }

  const mapOverlays = (operational: boolean): Record<string, RegionOverlay> => {
    const open = (building: string) => incidents.filter((i) => i.buildingId === building && !['RESOLVED', 'CLOSED'].includes(i.status)).length
    return {
      'bld-arb': { state: 'AFFECTED', badge: operational ? open('B-ARB') : undefined, caption: operational ? 'Power and Wi-Fi' : 'Some rooms closed' },
      'bld-klh': { state: 'MAINTENANCE', badge: operational ? open('B-KLH') : undefined, caption: operational ? 'Plumbing repair' : 'Repair work' },
      'bld-caf': { state: 'CLOSED', caption: 'Deep cleaning' },
      'bld-rlb': { state: 'OPEN', badge: operational ? open('B-RLB') : undefined },
    }
  }

  const bookingCheck = (body: { roomCode: string; start: string; end: string; headcount: number }): BookingCheck => {
    const room = roomByCode(body.roomCode)
    const findings: Finding[] = []
    const affected: BookingCheck['affectedClasses'] = []
    if (!room) {
      findings.push({ code: 'ROOM_UNKNOWN', severity: 'HARD', message: `There is no room ${body.roomCode}.`, affected: body.roomCode })
    } else {
      const startHour = new Date(body.start).getHours() + new Date(body.start).getMinutes() / 60
      const endHour = new Date(body.end).getHours() + new Date(body.end).getMinutes() / 60
      if (room.code.startsWith('ARB-2')) {
        findings.push({ code: 'ROOM_CLOSED', severity: 'HARD', message: `${room.code} has no power and is closed until INC-1041 is resolved.`, affected: room.code })
        if (room.code === 'ARB-204' && startHour < 12 && endHour > 9) {
          findings.push({ code: 'ROOM_OVERLAP', severity: 'HARD', message: 'ARB-204 is booked 09:00 to 12:00 for the CSE-3A Operating Systems exam.', affected: room.code })
          affected.push({ course: 'Operating Systems end semester', group: 'CSE-3A', headcount: 58, start: '09:00', end: '12:00' })
        }
      }
      if (body.headcount > room.capacity) {
        findings.push({ code: 'ROOM_CAPACITY', severity: 'HARD', message: `${room.code} seats ${room.capacity}, and you need ${body.headcount}.`, affected: room.code })
      }
      if (room.type === 'CLASSROOM' && body.headcount > 0 && body.headcount <= 30 && endHour - startHour >= 2 && room.features.includes('PROJECTOR') === false) {
        findings.push({ code: 'ROOM_TYPE', severity: 'SOFT', message: 'This is a practical-length booking in a plain classroom.', affected: room.code })
      }
    }
    const blocked = findings.some((finding) => finding.severity === 'HARD')
    const alternatives = blocked
      ? campus.rooms
          .filter((candidate) => candidate.bookable && candidate.status === 'OPEN' && !candidate.code.startsWith('ARB-2') && candidate.capacity >= body.headcount && candidate.type === (room?.type ?? 'CLASSROOM'))
          .sort((a, b) => Number(b.buildingId === room?.buildingId) - Number(a.buildingId === room?.buildingId) || a.capacity - b.capacity)
          .slice(0, 4)
          .map((candidate) => ({
            roomCode: candidate.code,
            type: candidate.type,
            capacity: candidate.capacity,
            building: buildingById(candidate.buildingId)?.name ?? '',
            fit: candidate.buildingId === room?.buildingId ? 'Same building, free then' : 'Free then, short walk',
          }))
      : []
    return { allowed: !blocked, findings, alternatives, affectedClasses: affected }
  }

  const slaSummary = () => {
    const rows = buildSlaRows()
    const count = (state: string) => rows.filter((row) => row.state === state).length
    return { onTrack: count('ON_TRACK'), atRisk: count('AT_RISK'), breached: count('BREACHED'), paused: count('PAUSED'), compliance: 87 }
  }

  return [
    // ---- campus and map ---------------------------------------------------------------------
    http.get(`${BASE}/campus/map`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      await lag()
      const operational = role === 'DEPARTMENT_MANAGER' || role === 'FACILITIES_ADMIN' || role === 'SYSTEM_ADMIN'
      const markers = operational
        ? incidents
            .filter((incident) => !['RESOLVED', 'CLOSED'].includes(incident.status) && incident.regionId)
            .map((incident, index) => {
              const centre = regionCentre(incident.regionId)
              return { id: incident.id, x: centre.x - 40 + index * 22, y: centre.y + 6, label: `${incident.id} ${incident.title}`, tone: incident.priority === 'P1' ? ('danger' as const) : ('warning' as const) }
            })
        : []
      return HttpResponse.json({ viewBox: campus.map.viewBox, decor: campus.map.decor, regions: campus.map.regions, overlays: mapOverlays(operational), markers, view: operational ? 'OPERATIONAL' : 'PUBLIC' })
    }),
    http.get(`${BASE}/campus/buildings/:id`, async ({ params, request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const building = campus.buildings.find((item) => item.id === params.id || item.mapRegionId === params.id)
      if (!building) return problem(404, 'NOT_FOUND', 'Building was not found.')
      const operational = role === 'DEPARTMENT_MANAGER' || role === 'FACILITIES_ADMIN' || role === 'SYSTEM_ADMIN'
      const rooms = campus.rooms
        .filter((room) => room.buildingId === building.id)
        .map((room) => ({ code: room.code, type: room.type, capacity: room.capacity, features: room.features, status: room.code.startsWith('ARB-2') ? 'CLOSED' : 'OPEN', note: room.code.startsWith('ARB-2') ? 'No power, INC-1041' : null }))
      return HttpResponse.json({
        id: building.id,
        name: building.name,
        code: building.code,
        kind: building.kind,
        status: mapOverlays(operational)[building.mapRegionId]?.state ?? 'OPEN',
        openingHours: building.openingHours,
        floors: building.floors,
        department: departmentName(building.departmentId),
        assetCount: operational ? building.assetCount : null,
        rooms: operational ? rooms : [],
        roomCount: rooms.length,
        incidents: operational ? incidents.filter((incident) => incident.buildingId === building.id && !['RESOLVED', 'CLOSED'].includes(incident.status)).map((incident) => ({ id: incident.id, title: incident.title, priority: incident.priority, status: incident.status })) : [],
      })
    }),
    http.get(`${BASE}/campus/rooms`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const url = new URL(request.url)
      const bookable = url.searchParams.get('bookable') === 'true'
      return HttpResponse.json(
        campus.rooms
          .filter((room) => !bookable || room.bookable)
          .map((room) => ({ code: room.code, type: room.type, capacity: room.capacity, building: buildingById(room.buildingId)?.name ?? '', features: room.features, status: room.code.startsWith('ARB-2') ? 'CLOSED' : 'OPEN', closedReason: room.code.startsWith('ARB-2') ? 'No power (INC-1041)' : null })),
      )
    }),
    http.get(`${BASE}/campus/resources`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const rooms = campus.rooms.filter((room) => room.departmentId === 'D-CSE')
      return HttpResponse.json({
        department: 'Computer Science',
        rooms: rooms.map((room) => ({ code: room.code, type: room.type, capacity: room.capacity, building: buildingById(room.buildingId)?.name ?? '', status: room.code.startsWith('ARB-2') ? 'CLOSED' : 'OPEN' })),
        assets: campus.keyAssets.filter((asset) => asset.buildingId === 'B-ARB').map((asset) => ({ id: asset.id, name: asset.name, category: asset.category, status: asset.id === 'AST-DB-ARB-F2' || asset.id === 'AST-SW-ARB-F2' ? 'FAULT' : 'OK' })),
        technicians,
      })
    }),
    http.get(`${BASE}/admin/campus/summary`, () =>
      HttpResponse.json({
        totals: { buildings: campus.buildings.length, rooms: campus.rooms.length, assets: campus.buildings.reduce((sum, b) => sum + b.assetCount, 0) },
        buildings: campus.buildings.map((building) => ({ id: building.id, code: building.code, name: building.name, kind: building.kind, floors: building.floors, rooms: campus.rooms.filter((room) => room.buildingId === building.id).length, assets: building.assetCount, regionBound: true, status: building.mapRegionId === 'bld-caf' ? 'CLOSED' : building.mapRegionId === 'bld-klh' ? 'MAINTENANCE' : 'OPEN' })),
      }),
    ),

    // ---- intake ------------------------------------------------------------------------------
    http.post(`${BASE}/issues/extract`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const { text } = (await request.json()) as { text: string }
      await lag()
      return HttpResponse.json(extract(text, incidents))
    }),
    http.post(`${BASE}/issues`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const body = (await request.json()) as { text: string; extraction: Extraction; channel?: 'FORM' | 'CHAT' }
      await lag()
      reportSequence += 1
      const duplicate = body.extraction.duplicate ? incidents.find((incident) => incident.id === body.extraction.duplicate!.incidentId) : undefined
      let incidentId = duplicate?.id
      if (duplicate) {
        duplicate.reportCount += 1
        duplicate.channels[body.channel ?? 'FORM'] += 1
      } else {
        incidentId = `INC-${incidentSequence++}`
      }
      const report: ReportSummary = {
        id: `R-${reportSequence}`,
        incidentId: incidentId ?? '',
        title: body.text.length > 70 ? `${body.text.slice(0, 67)}...` : body.text,
        status: 'ACKNOWLEDGED',
        priority: body.extraction.urgency === 'CRITICAL' ? 'P1' : body.extraction.urgency === 'HIGH' ? 'P2' : 'P3',
        channel: body.channel ?? 'FORM',
        submittedAt: clock.at(0),
        joinedExisting: !!duplicate,
        incidentReportCount: duplicate ? duplicate.reportCount : 1,
        summary: duplicate ? `This matches an incident that already exists, so your report was added to it. ${duplicate.reportCount} people have now reported it.` : 'Your report was received and sent to triage.',
        timeline: [{ id: 'a', title: 'You reported this', at: clock.at(0), tone: 'neutral' }],
        canGiveFeedback: false,
      }
      reports.unshift(report)
      return HttpResponse.json(report, { status: 201 })
    }),
    http.get(`${BASE}/issues/mine`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      return HttpResponse.json(reports)
    }),
    http.post(`${BASE}/issues/:id/feedback`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const report = reports.find((item) => item.id === params.id)
      if (report) report.canGiveFeedback = false
      return new HttpResponse(null, { status: 204 })
    }),
    http.get(`${BASE}/notices`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildNotices(clock)) : unauthenticated())),
    http.get(`${BASE}/inbox`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      return HttpResponse.json(emails)
    }),
    http.post(`${BASE}/inbox/simulate`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const body = (await request.json()) as { from: string; subject: string; text: string }
      const extraction = extract(`${body.subject}. ${body.text}`, incidents)
      const email: InboundEmail = {
        id: `EML-${7100 + emails.length}`,
        from: body.from || 'test.sender@example.com',
        subject: body.subject,
        body: body.text,
        receivedAt: clock.at(0),
        status: 'PENDING',
        extraction: { category: extraction.category, location: extraction.location.text || 'Unclear', urgency: extraction.urgency, asset: extraction.asset, confidence: extraction.categoryConfidence },
        incidentId: null,
        note: extraction.clarification ? 'The location is missing, so converting will send a clarification question.' : null,
      }
      emails.unshift(email)
      return HttpResponse.json(email, { status: 201 })
    }),
    http.post(`${BASE}/inbox/:id/process`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const email = emails.find((item) => item.id === params.id)
      if (!email) return problem(404, 'NOT_FOUND', 'Email was not found.')
      if (email.status !== 'PENDING') return HttpResponse.json(email)
      const unclear = !email.extraction || email.extraction.location === 'Unclear'
      if (unclear) {
        email.status = 'CLARIFICATION_SENT'
        email.note = 'A clarification question was sent: which room or building?'
      } else {
        const match = incidents.find((incident) => incident.category === email.extraction!.category && email.extraction!.location.includes(incident.buildingName.split(' ')[0]!))
        email.status = 'CONVERTED'
        email.incidentId = match?.id ?? `INC-${incidentSequence++}`
        email.note = match ? `Matched ${match.id}, so it was linked instead of creating a duplicate.` : 'A new incident was created.'
        if (match) match.reportCount += 1
      }
      return HttpResponse.json(email)
    }),

    // ---- incidents ---------------------------------------------------------------------------
    http.get(`${BASE}/incidents`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      await lag()
      const items = incidentsFor(role)
      return HttpResponse.json({ items, page: 0, size: 50, total: items.length })
    }),
    http.get(`${BASE}/incidents/:id`, ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const incident = incidents.find((item) => item.id === params.id)
      return incident ? HttpResponse.json(incident) : problem(404, 'NOT_FOUND', 'Incident was not found.')
    }),
    http.post(`${BASE}/incidents/:id/transition`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const incident = incidents.find((item) => item.id === params.id)
      if (!incident) return problem(404, 'NOT_FOUND', 'Incident was not found.')
      const { event } = (await request.json()) as { event: string }
      if (event === 'RESOLVE' && incident.unavailableActions.some((action) => action.key === 'incident.resolve')) {
        return problem(422, 'ILLEGAL_TRANSITION', incident.unavailableActions.find((action) => action.key === 'incident.resolve')!.reason)
      }
      incident.status = event === 'RESOLVE' ? 'RESOLVED' : incident.status
      return HttpResponse.json(incident)
    }),
    http.post(`${BASE}/incidents/:id/actions/:key`, ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const messages: Record<string, string> = {
        'incident.createWorkOrder': 'A work order was created and sent for assignment.',
        'incident.link': 'The reports were linked. Nobody who reported was lost.',
        'incident.close': 'The incident was closed and the reporters were told.',
      }
      return HttpResponse.json({ message: messages[String(params.key)] ?? 'Done.' })
    }),
    http.get(`${BASE}/cascading/impact/:id`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      return HttpResponse.json(buildImpact(String(params.id)))
    }),
    http.get(`${BASE}/timetable/today`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildTodaySessions()) : unauthenticated())),

    // ---- work orders and technicians ---------------------------------------------------------
    http.get(`${BASE}/work-orders`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      await lag()
      const items = workOrdersFor(role)
      return HttpResponse.json({ items, page: 0, size: 50, total: items.length })
    }),
    http.get(`${BASE}/work-orders/:id/candidates`, ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const order = workOrders.find((item) => item.id === params.id)
      return order ? HttpResponse.json(candidatesFor(order, technicians)) : problem(404, 'NOT_FOUND', 'Work order was not found.')
    }),
    http.post(`${BASE}/work-orders/:id/assign`, async ({ params, request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const order = workOrders.find((item) => item.id === params.id)
      if (!order) return problem(404, 'NOT_FOUND', 'Work order was not found.')
      const body = (await request.json()) as { technicianId: string; acknowledged?: boolean; overrideReason?: string }
      const candidate = candidatesFor(order, technicians).find((item) => item.technicianId === body.technicianId)
      const tech = technicians.find((item) => item.id === body.technicianId)
      if (!candidate || !tech) return problem(404, 'NOT_FOUND', 'Technician was not found.')
      if (candidate.decision === 'BLOCK') {
        collisions.unshift({ id: `CC-${5110 + collisions.length}`, at: clock.at(0), actionType: 'ASSIGN_TECHNICIAN', summary: `Assign ${order.id} to ${tech.name}`, actor: USER_NAME[role] ?? role, decision: 'BLOCK', findings: candidate.findings, override: null })
        return problem(422, 'COLLISION_BLOCKED', candidate.findings[0]?.message ?? 'This assignment is not allowed.', { decision: 'BLOCK', findings: candidate.findings })
      }
      if (candidate.decision === 'WARN' && !(body.acknowledged && body.overrideReason)) {
        return problem(409, 'COLLISION_WARNING', 'This assignment raises a warning that needs a reason.', { decision: 'WARN', findings: candidate.findings, requiresReason: true })
      }
      order.assignedTechnicianId = tech.id
      order.assignedTechnicianName = tech.name
      order.status = 'ASSIGNED'
      order.needsReassignment = null
      Object.assign(order, actionsFor(order.status))
      tech.openTasks += 1
      tech.workloadPercent = Math.round((tech.openTasks / tech.maxTasks) * 100)
      return HttpResponse.json(order)
    }),
    http.post(`${BASE}/work-orders/:id/:action`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const order = workOrders.find((item) => item.id === params.id)
      if (!order) return problem(404, 'NOT_FOUND', 'Work order was not found.')
      const body = (await request.json().catch(() => ({}))) as { reason?: string; notes?: string }
      const next: Record<string, WorkOrder['status']> = { accept: 'ACCEPTED', start: 'IN_PROGRESS', block: 'BLOCKED', complete: 'COMPLETED', resume: 'IN_PROGRESS' }
      const action = String(params.action)
      if (action === 'request-reassign') {
        order.needsReassignment = { reason: body.reason ?? 'Technician asked to be reassigned', suggestedTechnicianId: 'T-02', suggestedName: 'Meena Das' }
        return HttpResponse.json(order)
      }
      if (!next[action]) return problem(404, 'NOT_FOUND', 'Unknown action.')
      if (!order.availableActions.some((item) => item.key === `workorder.${action}`)) {
        return problem(422, 'ILLEGAL_TRANSITION', `Cannot ${action} while the status is ${order.status}.`)
      }
      if (action === 'complete' && !body.notes?.trim()) return problem(422, 'COMPLETION_NOTES_REQUIRED', 'Add a short note about what you did before completing.')
      order.status = next[action]!
      order.blockReason = action === 'block' ? 'WAITING_FOR_PARTS' : null
      Object.assign(order, actionsFor(order.status))
      return HttpResponse.json(order)
    }),
    http.get(`${BASE}/technicians`, ({ request }) => (roleOf(request) ? HttpResponse.json(technicians) : unauthenticated())),
    http.get(`${BASE}/technicians/me`, ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const me = technicians.find((item) => item.id === 'T-01')!
      return HttpResponse.json({ ...me, leave: [{ from: '2026-11-14', to: '2026-11-16', reason: 'Family function' }] })
    }),
    http.patch(`${BASE}/technicians/me/availability`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const { availability } = (await request.json()) as { availability: TechnicianCard['availability'] }
      const me = technicians.find((item) => item.id === 'T-01')!
      me.availability = availability
      const open = workOrders.filter((order) => order.assignedTechnicianId === 'T-01' && !['COMPLETED', 'VERIFIED'].includes(order.status))
      if (availability === 'SICK' || availability === 'ON_LEAVE') {
        for (const order of open) order.needsReassignment = { reason: `${me.name} is ${availability === 'SICK' ? 'off sick' : 'on leave'}`, suggestedTechnicianId: 'T-02', suggestedName: 'Meena Das' }
      } else {
        for (const order of open) order.needsReassignment = null
      }
      return HttpResponse.json({ availability, flaggedWorkOrders: availability === 'SICK' || availability === 'ON_LEAVE' ? open.length : 0 })
    }),
    http.get(`${BASE}/inventory/mine`, ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      return HttpResponse.json(workOrders.filter((order) => order.assignedTechnicianId === 'T-01').flatMap((order) => order.parts.map((part) => ({ ...part, workOrderId: order.id, workOrderTitle: order.title }))))
    }),
    http.get(`${BASE}/maintenance-history`, ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      return HttpResponse.json(campus.history.filter((record) => ['ELECTRICAL', 'EQUIPMENT'].includes(record.category)).slice(-12).reverse())
    }),

    // ---- constraint engines ------------------------------------------------------------------
    http.get(`${BASE}/collisions`, ({ request }) => (roleOf(request) ? HttpResponse.json(collisions) : unauthenticated())),
    http.post(`${BASE}/simulations`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const { incidentId } = (await request.json()) as { incidentId: string }
      await delay(import.meta.env.MODE === 'test' ? 0 : 700)
      return HttpResponse.json(buildSimulation(incidentId, makeClock()), { status: 201 })
    }),
    http.post(`${BASE}/simulations/:runId/plans/:planId/execute`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      const run = String(params.runId)
      if (executedPlans.size > 0 && !executedPlans.has(run)) {
        return HttpResponse.json({ status: 'STALE', message: 'Live data changed since this simulation, so nothing was executed. Run the simulation again.' })
      }
      executedPlans.add(run)
      return HttpResponse.json({ status: 'EXECUTED', message: 'Plan checked against live data again and applied. 58 students and 1 invigilator were notified.', notified: 59 })
    }),

    // ---- bookings ----------------------------------------------------------------------------
    http.get(`${BASE}/bookings`, ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const items = role === 'FACULTY' ? bookings.filter((b) => b.requester === 'Dr. Kiran Rao') : bookings
      return HttpResponse.json({ items, page: 0, size: 50, total: items.length })
    }),
    http.post(`${BASE}/bookings/check`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      return HttpResponse.json(bookingCheck((await request.json()) as Parameters<typeof bookingCheck>[0]))
    }),
    http.post(`${BASE}/bookings`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const body = (await request.json()) as { roomCode: string; start: string; end: string; headcount: number; purpose: string }
      const check = bookingCheck(body)
      if (!check.allowed) return problem(422, 'COLLISION_BLOCKED', check.findings[0]?.message ?? 'This booking is not allowed.', { decision: 'BLOCK', findings: check.findings })
      const room = roomByCode(body.roomCode)!
      const row: BookingRow = { id: `BK-${2300 + bookings.length}`, roomCode: room.code, roomType: room.type, building: buildingById(room.buildingId)?.name ?? '', purpose: body.purpose || 'Booking', start: body.start, end: body.end, status: 'CONFIRMED', requester: USER_NAME[role] ?? role, headcount: body.headcount, impact: 'LECTURE' }
      bookings.unshift(row)
      return HttpResponse.json(row, { status: 201 })
    }),
    http.post(`${BASE}/bookings/:id/cancel`, ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const booking = bookings.find((item) => item.id === params.id)
      if (booking) booking.status = 'CANCELLED'
      return HttpResponse.json(booking)
    }),

    // ---- inventory, approvals, procurement ---------------------------------------------------
    http.get(`${BASE}/inventory/items`, ({ request }) => (roleOf(request) ? HttpResponse.json(stock) : unauthenticated())),
    http.get(`${BASE}/approvals`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      await lag()
      const items = approvalsFor(role)
      return HttpResponse.json({ items, page: 0, size: 50, total: items.length })
    }),
    http.post(`${BASE}/approvals`, async ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const body = (await request.json()) as { type: Approval['type']; title: string; justification: string; amountPaise: number; linkedWorkOrderId?: string }
      const approval: Approval = {
        id: `APR-${620 + approvals.length}`,
        type: body.type,
        status: 'SUBMITTED',
        title: body.title,
        requesterName: USER_NAME[role] ?? role,
        requesterRole: role,
        amountPaise: body.amountPaise,
        justification: body.justification,
        linkedWorkOrderId: body.linkedWorkOrderId ?? null,
        linkedIncidentId: null,
        lines: [],
        evidence: [],
        routing: body.amountPaise > 2_500_000 && role === 'DEPARTMENT_MANAGER' ? 'Above the ₹25,000 Department Manager limit, so routed to Procurement.' : 'Routed to a Procurement Approver.',
        decisions: [],
        createdAt: clock.at(0),
        availableActions: [],
        unavailableActions: [],
      }
      approvals = [approval, ...approvals]
      return HttpResponse.json({ ...approval, ...approvalActions(approval, role) }, { status: 201 })
    }),
    http.post(`${BASE}/approvals/:id/decide`, async ({ params, request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const approval = approvals.find((item) => item.id === params.id)
      if (!approval) return problem(404, 'NOT_FOUND', 'Approval was not found.')
      const guard = approvalActions(approval, role)
      if (guard.availableActions.length === 0) {
        const reason = guard.unavailableActions[0]?.reason ?? 'You cannot decide this request.'
        return problem(422, reason.includes('raised') ? 'SELF_APPROVAL' : 'NOT_ALLOWED', reason)
      }
      const { decision, reason } = (await request.json()) as { decision: 'APPROVE' | 'REJECT' | 'CLARIFY'; reason?: string }
      approval.status = decision === 'APPROVE' ? 'APPROVED' : decision === 'REJECT' ? 'REJECTED' : 'NEEDS_CLARIFICATION'
      approval.decisions.push({ by: USER_NAME[role] ?? role, decision: decision === 'APPROVE' ? 'APPROVED' : decision === 'REJECT' ? 'REJECTED' : 'CLARIFICATION REQUESTED', reason: reason ?? null, at: clock.at(0) })
      return HttpResponse.json({ ...approval, ...approvalActions(approval, role) })
    }),
    http.get(`${BASE}/purchase-orders`, ({ request }) => (roleOf(request) ? HttpResponse.json(purchaseOrders) : unauthenticated())),
    http.get(`${BASE}/invoices`, ({ request }) => (roleOf(request) ? HttpResponse.json(invoices) : unauthenticated())),
    http.post(`${BASE}/invoices`, async ({ request }) => {
      if (!roleOf(request)) return unauthenticated()
      const { fileName } = (await request.json()) as { fileName: string }
      await delay(import.meta.env.MODE === 'test' ? 0 : 900)
      const invoice: Invoice = {
        id: `INV-${440 + invoices.length}`,
        supplier: 'Brightline Electricals',
        invoiceNumber: `BE/2026/${1200 + invoices.length}`,
        invoiceDate: '2026-10-30',
        purchaseOrderId: 'PO-884',
        status: 'MATCHED',
        totalPaise: 290000,
        fileName,
        extractionSource: 'AI',
        lines: [{ lineNo: 1, description: 'MCB 32A three pole', qty: 2, unitPaise: 145000, poQty: 2, poUnitPaise: 145000, match: 'OK', confidence: 0.96 }],
        discrepancies: [],
      }
      invoices.unshift(invoice)
      return HttpResponse.json(invoice, { status: 201 })
    }),
    http.post(`${BASE}/invoices/:id/resolve`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const invoice = invoices.find((item) => item.id === params.id)
      if (!invoice) return problem(404, 'NOT_FOUND', 'Invoice was not found.')
      const { code } = (await request.json()) as { code: string }
      invoice.discrepancies = invoice.discrepancies.map((item) => (item.code === code ? { ...item, resolved: true } : item))
      invoice.lines = invoice.lines.map((line) => ((code === 'PRICE_MISMATCH' && line.match === 'PRICE') || (code === 'EXTRA_LINE' && line.match === 'EXTRA') ? { ...line, match: 'OK' as const } : line))
      if (invoice.discrepancies.every((item) => item.resolved)) invoice.status = 'MATCHED'
      return HttpResponse.json(invoice)
    }),
    http.post(`${BASE}/invoices/:id/validate`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const invoice = invoices.find((item) => item.id === params.id)
      if (!invoice) return problem(404, 'NOT_FOUND', 'Invoice was not found.')
      if (invoice.status === 'DISCREPANCY') return problem(422, 'DISCREPANCIES_OPEN', 'Resolve every discrepancy before validating this invoice.')
      if (invoice.status === 'MATCHED') invoice.status = 'VALIDATED'
      return HttpResponse.json(invoice)
    }),
    http.get(`${BASE}/goods-receipts`, ({ request }) => (roleOf(request) ? HttpResponse.json(receipts) : unauthenticated())),
    http.post(`${BASE}/goods-receipts/:id/validate`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const receipt = receipts.find((item) => item.id === params.id)
      if (!receipt) return problem(404, 'NOT_FOUND', 'Receipt was not found.')
      const replay = postedReceipts.get(receipt.id)
      if (replay) return HttpResponse.json({ posted: true, replayed: true, ledgerEntries: replay, message: 'This receipt was already posted. Nothing changed.' })
      const invoice = invoices.find((item) => item.id === receipt.invoiceId)
      if (invoice && invoice.status !== 'MATCHED' && invoice.status !== 'VALIDATED') {
        return problem(422, 'INVOICE_NOT_VALIDATED', `Invoice ${invoice.id} still has open discrepancies. Resolve and validate it first.`)
      }
      const entries = receipt.lines.map((line) => ({ sku: line.name, qty: line.received }))
      for (const line of receipt.lines) {
        const row = stock.find((item) => item.name === line.name)
        if (row) {
          row.onHand += line.received
          row.available += line.received
          row.status = row.onHand === 0 ? 'OUT' : row.onHand <= row.threshold ? 'LOW' : 'OK'
        }
      }
      receipt.status = 'VALIDATED'
      if (invoice) invoice.status = 'POSTED'
      postedReceipts.set(receipt.id, entries)
      return HttpResponse.json({ posted: true, replayed: false, ledgerEntries: entries, message: 'Stock posted once, with your name, the time and this receipt as the source.' })
    }),

    // ---- SLA, analytics ----------------------------------------------------------------------
    http.get(`${BASE}/sla/instances`, ({ request }) => {
      const role = roleOf(request)
      if (!role) return unauthenticated()
      const rows = buildSlaRows()
      return HttpResponse.json(role === 'DEPARTMENT_MANAGER' ? rows.filter((row) => ['INC-1041', 'INC-1042', 'WO-210'].includes(row.subjectId)) : rows)
    }),
    http.get(`${BASE}/sla/summary`, ({ request }) => (roleOf(request) ? HttpResponse.json(slaSummary()) : unauthenticated())),
    http.get(`${BASE}/analytics/overview`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildAnalytics()) : unauthenticated())),

    // ---- administration ----------------------------------------------------------------------
    http.get(`${BASE}/admin/system/health`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildHealth(clock)) : unauthenticated())),
    http.get(`${BASE}/admin/staff`, ({ request }) => (roleOf(request) ? HttpResponse.json({ technicians, faculty: campus.faculty.map((person) => ({ id: person.id, name: person.name, department: departmentName(person.departmentId), kind: person.kind })) }) : unauthenticated())),
    http.get(`${BASE}/admin/rules`, ({ request }) => (roleOf(request) ? HttpResponse.json(rules) : unauthenticated())),
    http.patch(`${BASE}/admin/rules/:id`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const rule = rules.find((item) => item.id === params.id)
      if (!rule) return problem(404, 'NOT_FOUND', 'Rule was not found.')
      if (rule.locked) return problem(422, 'RULE_LOCKED', `${rule.name} protects a safety guarantee and cannot be switched off.`)
      const { enabled } = (await request.json()) as { enabled: boolean }
      rule.enabled = enabled
      return HttpResponse.json(rule)
    }),
    http.get(`${BASE}/admin/sla-policies`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildSlaPolicies()) : unauthenticated())),
    http.get(`${BASE}/admin/integrations`, ({ request }) => (roleOf(request) ? HttpResponse.json(integrations) : unauthenticated())),
    http.patch(`${BASE}/admin/integrations/features/:key`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      const feature = integrations.ai.features.find((item) => item.key === params.key)
      if (!feature) return problem(404, 'NOT_FOUND', 'Feature was not found.')
      const { enabled } = (await request.json()) as { enabled: boolean }
      feature.enabled = enabled
      feature.mode = enabled ? 'AI' : 'RULES'
      return HttpResponse.json(integrations)
    }),
    http.post(`${BASE}/admin/webhooks/:id/test`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      await lag()
      const hook = integrations.webhooks.find((item) => item.id === params.id)
      if (hook) {
        hook.lastStatus = 200
        hook.lastAt = clock.at(0)
      }
      return HttpResponse.json({ status: 200, signed: true, message: 'Delivered with a signature. Sending the same event again is ignored by the receiver.' })
    }),
    http.get(`${BASE}/admin/scenarios`, ({ request }) => (roleOf(request) ? HttpResponse.json(buildScenarios()) : unauthenticated())),
    http.post(`${BASE}/admin/scenarios/:id/reset`, async ({ params, request }) => {
      if (!roleOf(request)) return unauthenticated()
      await delay(import.meta.env.MODE === 'test' ? 0 : 800)
      return HttpResponse.json({ ok: true, message: `The campus is back to Scenario ${String(params.id)}. Times were moved to now.` })
    }),
  ]
}
