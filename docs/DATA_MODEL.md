# UNIO — Data Model

Database: MongoDB Atlas (PS constraint C1). Campus content is fictional (C2).

## 1. Conventions

- **Ids:** human-readable string `_id` with a type prefix (`INC-1042`, `WO-104`,
  `BK-2201`). They read well in a demo and in audit logs.
- **Time:** UTC in storage, local time in the UI.
- **Every mutable aggregate carries** `version` (long), `createdAt`, `updatedAt`.
- **State changes are compare-and-set:** `updateOne({_id, version, status}, ...)`. If
  zero documents match, the caller re-reads and re-validates. This covers C4 and works
  without multi-document transactions.
- **Money:** integer paise, never floats.
- **Enums** live in Python and are mirrored to TypeScript through the generated OpenAPI types.
- **API DTOs never expose documents directly.** See the projections in
  `RBAC_AND_NAVIGATION.md` §5.
- **Do not store derived values** such as "available stock". Compute them.

## 2. Concurrency: guarantees that come from the database

Atlas M0 transaction support is checked in Phase 1 and must not be assumed. These
protections hold either way, because each one relies on a single-document atomic write
or a unique index.

| Guarantee | Mechanism |
|---|---|
| No room double-booking | Unique index on `room_slots {roomId, slotStart}` |
| No technician double-assignment | Unique index on `technician_slots {technicianId, slotStart}` |
| No overselling stock | Conditional `$inc` on `inventory_balances` |
| No double stock posting | Unique index on `inventory_transactions.postingKey` |
| Duplicate email ignored | Unique index on `inbound_emails.messageId` |
| Duplicate webhook ignored | Unique index on `webhook_inbound_events {source, eventId}` |
| Duplicate notification avoided | Unique index on `notifications.dedupeKey` |
| Escalation fires once | Unique index on `sla_escalations {slaInstanceId, level}` |
| Retried POST returns the first result | Unique index on `idempotency_keys.key` |
| Duplicate invoice rejected | Unique index on `invoices {supplierId, invoiceNumber}` |

### Slot claims

Time is cut into 15-minute slots. A booking claims one document per slot, and the
unique index decides the winner under concurrency.

```js
// room_slots
{ _id: ObjectId, roomId: "RM-A204", slotStart: ISODate("2026-11-03T09:00:00Z"),
  holderType: "BOOKING",   // BOOKING | SESSION | MAINTENANCE | CLOSURE
  holderId: "BK-2201", createdAt: ISODate("...") }
```

Flow: run the Collision Engine for the explanation, then `insertMany(ordered=true)` the
claims. On a duplicate-key error, delete the claims for this `holderId` and return
`ROOM_OVERLAP`. Timetable sessions, maintenance windows and closures all claim slots
too, so one index covers every source of room conflict. `technician_slots` uses the
same pattern. Claims are released on cancel, completion or reassignment.

### Stock reservation

```js
db.inventory_balances.updateOne(
  { itemId: "ITM-MCB-32A", locationId: "LOC-MAIN",
    $expr: { $gte: [ { $subtract: ["$onHand", "$reserved"] }, 4 ] } },
  { $inc: { reserved: 4, version: 1 }, $set: { updatedAt: new Date() } })
// modifiedCount == 0 -> insufficient stock -> flag work order BLOCKED (M6)
```

## 3. Collections

### Identity and access

```js
// users
{ _id: "U-041", name, email /*unique*/, passwordHash, roleKey: "TECHNICIAN",
  departmentId, managedDepartmentIds: [], campusId: "CAMPUS-1",
  approvalLimitPaise: 0,
  flags: { procurementRequester: false },
  status: "ACTIVE", lastLoginAt, version, createdAt, updatedAt }

// roles_permissions
{ _id: "TECHNICIAN", label, workspace: "technician", accent: "amber",
  permissions: ["issue.create", "..."], scopes: { WORK_ORDER: "ASSIGNED" }, version }
```

### Campus master data (M3)

```js
// departments
{ _id: "D-ELEC", name, code, managerId, kind: "ACADEMIC" /* or FACILITY */ }

// buildings: mapRegionId binds the document to a region in the campus SVG
{ _id: "B-A", name: "Aryabhata Block", code: "ARB", mapRegionId: "bld-arb",
  status: "OPEN", floors: 4 }

// floors
{ _id: "F-A2", buildingId: "B-A", number: 2, name: "Second Floor" }

// rooms
{ _id: "RM-A204", buildingId: "B-A", floorId: "F-A2", code: "ARB-204",
  type: "CLASSROOM", /* LAB | SEMINAR | HALL | OFFICE | HOSTEL | COMMON */
  capacity: 60, features: ["PROJECTOR"], departmentId: "D-CSE",
  status: "OPEN", mapRegionId: "rm-arb-204", bookable: true }

// assets
{ _id: "AST-AP-A2-01", assetCode, name: "Wi-Fi AP A2-01", category: "NETWORK",
  roomId, buildingId, status: "OK", installedAt, lastServicedAt, criticality: 3 }

// dependency_edges: the Cascading Event Intelligence graph (see §6)
{ _id: ObjectId, fromType: "ASSET", fromId: "AST-SW-A-CORE",
  toType: "ASSET", toId: "AST-AP-A2-01",
  relation: "POWERS",  // POWERS | CONNECTS | CONTAINS | SERVES | LOCATED_IN
  source: "SEED", active: true }

// maintenance_history (M3)
{ _id: ObjectId, assetId, roomId, workOrderId, category, summary,
  technicianId, completedAt, partsUsed: [{ itemId, qty }], costPaise }
```

### Academic schedule (needed for M5 "affected classes")

```js
// timetable_sessions: expanded instances, one document per occurrence
{ _id: "SES-88012", courseCode, courseName, kind: "EXAM",
  /* LECTURE | PRACTICAL | EXAM | EVENT */
  roomId, facultyId, departmentId, studentGroup: "CSE-3A", headcount: 58,
  startAt, endAt, status: "SCHEDULED" }

// student_groups
{ _id: "CSE-3A", departmentId, memberIds: ["U-101", "..."] }
```

### Intake (M1)

```js
// conversations: chat intake, a deterministic slot-filling state machine
{ _id: "CNV-301", userId, status: "COLLECTING",
  /* COLLECTING | CONFIRMING | SUBMITTED | ABANDONED */
  slots: { issueType, locationRoomId, urgency, assetId },
  missingSlots: ["locationRoomId"],
  messages: [{ role: "USER", text, at }, { role: "SYSTEM", text, at }],
  reportId: null, version }

// inbound_emails: the simulated inbox (C5)
{ _id: "EML-7001", messageId /*unique*/, from, subject, bodyText, receivedAt,
  processingStatus: "PENDING",
  /* PENDING | PROCESSING | CLARIFICATION_SENT | CONVERTED | IGNORED | FAILED */
  attempts: 0, reportId: null, inReplyTo: null, senderUserId: null }

// reports: one per submission. The original text is never overwritten.
{ _id: "RPT-5501", channel: "FORM", /* CHAT | EMAIL */
  reporterId, originalText, attachments: [{ fileId, mime, sizeBytes }],
  roomId, buildingId, assetId,
  extracted: { category, urgency, assetName, locationText },
  extractionSuggestionId: "AIS-9001",
  clarification: { needed: false, questions: [] },
  incidentId: "INC-1042",
  linkType: "PRIMARY", /* DUPLICATE | RELATED */
  embedding: [/* 384 floats, excluded from API projections */],
  embeddingModel: "minilm-l6-v2-onnx", createdAt }

// ai_suggestions: every model output, kept apart from authoritative fields (C6)
{ _id: "AIS-9001", kind: "TRIAGE", /* DUPLICATE | SUMMARY | INVOICE | SLA_RISK */
  subjectType: "REPORT", subjectId: "RPT-5501",
  output: { }, confidence: 0.91, modelVersion: "triage-1.0.0",
  source: "ML", /* LLM | RULE */
  decision: "PENDING", /* ACCEPTED | CORRECTED | REJECTED */
  decidedBy: null, correction: null, createdAt }
```

### Incidents (M2)

```js
// incidents
{ _id: "INC-1042", title, category: "NETWORK", priority: "P1", status: "ACKNOWLEDGED",
  campusId, departmentId, buildingId, roomIds: [], assetIds: [],
  reporterIds: [], reportCount: 14,
  summary: { text, suggestionId, generatedAt, basedOnReportCount: 14 },
  dependencyRootId: "AST-SW-A-CORE", clusterKey,
  impactSnapshotId, slaInstanceId, workOrderIds: [],
  timeline: [{ at, actorId, event, note }],
  version, createdAt, updatedAt, resolvedAt, closedAt }

// incident_relations
{ _id: ObjectId, sourceIncidentId, targetType: "INCIDENT", targetId,
  relationType: "DUPLICATE_OF", /* RELATED_TO | CAUSED_BY */
  confidence: 0.93, source: "ML", /* RULE | HUMAN */ decidedBy, createdAt }

// impact_snapshots: output of Cascading Event Intelligence
{ _id: "IMP-300", incidentId, generatedAt, graphVersion,
  chain: [{ depth: 2, entityType: "ROOM", entityId: "RM-A204",
            viaEdge: "LOCATED_IN", reason, severity: "HIGH", score: 86 }],
  totals: { rooms: 6, sessions: 3, exams: 1, people: 212, workOrders: 2 } }
```

### Bookings (M5)

```js
// bookings
{ _id: "BK-2201", roomId, requesterId, departmentId, startAt, endAt, purpose,
  headcount, academicImpact: "EXAM", status: "CONFIRMED",
  rescheduledFromId: null, collisionCheckId, version, createdAt, updatedAt }
```

### Work orders and technicians (M4)

```js
// technicians
{ _id: "T-08", userId, departmentId, skills: [{ code: "ELECTRICAL", level: 3 }],
  availability: "AVAILABLE", /* ON_LEAVE | SICK | OFF_SHIFT */
  availabilityChangedAt, maxConcurrentTasks: 3, version }

// shifts
{ _id: ObjectId, technicianId, startAt, endAt, kind: "REGULAR" }

// work_orders
{ _id: "WO-104", incidentId, title, category, priority, status: "BLOCKED",
  blockReason: "WAITING_FOR_PARTS", roomId, buildingId, assetId, departmentId,
  requiredSkills: [{ code: "ELECTRICAL", minLevel: 2 }],
  estimatedMinutes: 90, scheduledStartAt, scheduledEndAt,
  assignedTechnicianId, assignmentScore: { total, factors: [] },
  partRequirements: [{ itemId, qty, reservationId, state: "SHORT" }],
  estimatedCostPaise, approvalIds: [], slaInstanceId,
  completion: { notes, evidenceFileIds: [], completedAt, verifiedBy },
  version, createdAt, updatedAt }

// work_order_events: append-only
{ _id: ObjectId, workOrderId, eventType, fromStatus, toStatus, actorId, actorRole,
  notes, at, correlationId }
```

### Inventory (M6)

```js
// inventory_items
{ _id: "ITM-MCB-32A", sku, name, category, unit: "EA", reorderThreshold: 5,
  critical: true, unitCostPaise: 42000 }

// stock_locations
{ _id: "LOC-MAIN", name, departmentId: null }

// inventory_balances: unique {itemId, locationId}
{ _id: ObjectId, itemId, locationId, onHand: 12, reserved: 8, version, updatedAt }

// reservations
{ _id: "RSV-77", itemId, locationId, qty, workOrderId,
  status: "ACTIVE", /* FULFILLED | RELEASED */ createdBy, createdAt }

// inventory_transactions: immutable ledger
{ _id: ObjectId, postingKey /*unique*/, itemId, locationId, qtyDelta,
  type: "RECEIPT", /* ISSUE | ADJUSTMENT | RETURN */
  sourceType: "GOODS_RECEIPT", sourceId, lineNo, actorId, at, balanceApplied: true }
```

`postingKey` is `sourceType:sourceId:lineNo`, so re-submitting a receipt cannot post
twice. The ledger row is inserted with `balanceApplied:false`, the balance is
incremented, and the flag is then set. A startup reconciler finishes any row left false
by a crash. If Phase 1 confirms transactions on our Atlas tier, wrap the steps in one.

### Approvals and procurement (M7)

One polymorphic framework for all three approval types.

```js
// approvals
{ _id: "APR-610", type: "PURCHASE", /* COSTLY_REPAIR | OVERRIDE */
  status: "UNDER_REVIEW",
  /* DRAFT | SUBMITTED | UNDER_REVIEW | NEEDS_CLARIFICATION | APPROVED | REJECTED | EXECUTED | STALE */
  requesterId, requesterRole, departmentId, amountPaise, justification,
  subject: { workOrderId, incidentId, collisionCheckId, items: [{ itemId, qty, estPaise }] },
  routing: { rule: "AMOUNT_ABOVE_LIMIT", requiredPermission: "approval.decide.purchase" },
  decisions: [{ deciderId, decision, reason, at }],
  executionCheck: { checkedAt, result, stateVersion },
  version, createdAt, updatedAt }

// approval_rules: the configurable matrix
{ _id: "RULE-1", type: "COSTLY_REPAIR", minPaise: 2500000, maxPaise: null,
  deciderRoles: ["FACILITIES_ADMIN", "PROCUREMENT_APPROVER"] }

// suppliers (fictional)
{ _id: "SUP-3", name, gstin, contactEmail }

// purchase_orders
{ _id: "PO-881", approvalId, supplierId, lines: [{ lineNo, itemId, qty, unitPricePaise }],
  totalPaise, status: "ORDERED", version, createdAt }

// invoices: unique {supplierId, invoiceNumber}
{ _id: "INV-431", supplierId, invoiceNumber, invoiceDate, fileId, purchaseOrderId,
  status: "DISCREPANCY",
  extraction: { suggestionId, fieldConfidence: { invoiceNumber: 0.98 } },
  lines: [{ lineNo, itemId, descriptionText, qty, unitPricePaise, taxPaise, totalPaise }],
  discrepancies: [{ code: "PRICE_MISMATCH", lineNo, expected, actual, resolved: false }],
  validatedBy: null, version, createdAt }

// goods_receipts
{ _id: "GR-92", purchaseOrderId, invoiceId, verifierId,
  lines: [{ lineNo, itemId, qtyReceived, qtyAccepted, locationId }],
  status: "PENDING", /* VALIDATED | REJECTED */ validatedAt, version }
```

The verifier must differ from the requester of the linked approval. An invoice can
never post stock. Only validating a goods receipt writes `inventory_transactions`.

### Constraint engines

```js
// collision_checks
{ _id: "CC-5100", actionType: "ASSIGN_TECHNICIAN", proposedAction: {}, actorId,
  stage: "COMMIT", /* PREVIEW | COMMIT | SIMULATION */
  stateVersion, decision: "BLOCK", /* ALLOW | WARN | REQUIRE_APPROVAL | BLOCK */
  findings: [{ code: "TECHNICIAN_OVERLAP", severity: "HARD", message,
               affected: [{ type: "TECHNICIAN", id: "T-08" }], ruleId: "TECH-002" }],
  alternatives: [], overrideApprovalId: null, createdAt }

// collision_rules: configurable by the System Administrator
{ _id: "TECH-003", actionTypes: ["ASSIGN_TECHNICIAN"], severity: "SOFT",
  enabled: true, params: { maxConcurrent: 3 }, description }

// simulation_runs: the ONLY writes a simulation makes (see §5)
{ _id: "SIM-77", incidentId, createdBy, snapshot: { version, takenAt, hash },
  plans: [{ planId: "A", label, actions: [], feasible: false,
            findings: [], metrics: { roomsAffected, peopleMoved, slaMarginMinutes,
                                     partsUsed, staffMinutes } }],
  recommendedPlanId: "B", selectedPlanId: null, executionResult: null, createdAt }
```

### SLA, notifications, integrations, audit (M8, C5)

```js
// sla_policies
{ _id: "SLA-NET-P1", category: "NETWORK", priority: "P1",
  responseTargetMin: 15, resolutionTargetMin: 240, atRiskPct: 75,
  pausable: true, pauseReasons: ["WAITING_FOR_PARTS"],
  escalations: [{ level: 1, atPct: 75, notifyRoles: ["DEPARTMENT_MANAGER"] },
                { level: 2, atPct: 100, notifyRoles: ["FACILITIES_ADMIN"] }] }

// sla_instances
{ _id: "SLI-901", subjectType: "INCIDENT", subjectId, policyId, startedAt,
  responseDueAt, resolutionDueAt, respondedAt, resolvedAt, pausedMinutes: 0,
  pauses: [{ from, to, reason, actorId }], state: "AT_RISK",
  /* ON_TRACK | AT_RISK | BREACHED | PAUSED | MET */
  riskSuggestionId, version }

// sla_escalations: unique {slaInstanceId, level}
{ _id: ObjectId, slaInstanceId, level, firedAt, notifiedUserIds: [] }

// notifications: unique dedupeKey
{ _id: ObjectId, dedupeKey, recipientId, type, title, message,
  entityRef: { type, id }, channel: "IN_APP", readAt, createdAt }

// outbox_events: written with the business change, sent asynchronously
{ _id: ObjectId, eventType: "incident.resolved", payload: {}, createdAt,
  dispatchedAt: null, attempts: 0 }

// webhook_endpoints and webhook_deliveries (outbound)
{ _id: "WH-1", url, secretRef, eventTypes: [], enabled: true }
{ _id: ObjectId, endpointId, eventId, attempt, statusCode, responseMs, sentAt }

// webhook_inbound_events: unique {source, eventId}
{ _id: ObjectId, source, eventId, payload: {}, receivedAt, processed: true }

// audit_logs: append-only, no update or delete code path exists
{ _id: ObjectId, actorId, actorRole, action, entityType, entityId,
  before: {}, after: {}, reason, approvalId, correlationId, at }

// idempotency_keys: TTL 24h on createdAt, unique key
{ _id: ObjectId, key, userId, route, requestHash, status: "COMPLETED",
  responseStatus: 201, responseBody: {}, createdAt }

// file_objects: metadata only, bytes live in object storage
{ _id: "FILE-1", storageKey, mime, sizeBytes, purpose: "EVIDENCE", ownerId,
  entityRef: { type, id }, createdAt }

// campus_map: metadata for the fictional SVG
{ _id: "MAP-1", svgPath: "/campus/unio-campus.svg", version: 1,
  regions: [{ regionId: "bld-arb", entityType: "BUILDING", entityId: "B-A" }] }

// demo_scenarios: drives one-click reset
{ _id: "SCENARIO-A", label, description, seedFile: "scenario-a.json", clock: {} }
```

## 4. Indexes

| Collection | Index | Purpose |
|---|---|---|
| `users` | `{email:1}` unique | Login |
| `room_slots` | `{roomId:1, slotStart:1}` unique; `{holderId:1}` | Double-booking guard, release |
| `technician_slots` | `{technicianId:1, slotStart:1}` unique; `{holderId:1}` | Assignment guard |
| `timetable_sessions` | `{roomId:1, startAt:1}`; `{facultyId:1, startAt:1}` | Affected classes |
| `reports` | `{incidentId:1}`; `{buildingId:1, createdAt:-1}`; `{reporterId:1, createdAt:-1}` | Linking, duplicate gating |
| `incidents` | `{status:1, priority:1, createdAt:-1}`; `{buildingId:1, status:1}`; `{departmentId:1, status:1}`; `{reporterIds:1}` | Queues, scope |
| `work_orders` | `{assignedTechnicianId:1, status:1}`; `{departmentId:1, status:1}`; `{status:1, priority:1}` | Queues, scope |
| `dependency_edges` | `{fromType:1, fromId:1, active:1}`; `{toType:1, toId:1, active:1}` | Traversal |
| `inventory_balances` | `{itemId:1, locationId:1}` unique | Stock |
| `inventory_transactions` | `{postingKey:1}` unique; `{itemId:1, at:-1}` | Ledger |
| `approvals` | `{status:1, type:1, createdAt:-1}`; `{requesterId:1, createdAt:-1}` | Queues |
| `invoices` | `{supplierId:1, invoiceNumber:1}` unique | Duplicate invoice |
| `sla_instances` | `{state:1, resolutionDueAt:1}` | Sweep |
| `notifications` | `{dedupeKey:1}` unique; `{recipientId:1, readAt:1, createdAt:-1}` | Inbox |
| `inbound_emails` | `{messageId:1}` unique; `{processingStatus:1, receivedAt:1}` | Inbox |
| `outbox_events` | `{dispatchedAt:1, createdAt:1}` | Dispatcher |
| `audit_logs` | `{entityType:1, entityId:1, at:-1}`; `{actorId:1, at:-1}` | Trail |
| `idempotency_keys` | `{key:1}` unique; TTL on `createdAt` | Repeated requests |

Create indexes in code at startup. `reports.embedding` stays out of list projections.

## 5. Simulation isolation

The simulator reads through a `SnapshotReader` built in memory, and only that reader is
passed to the Collision Engine. Its package has no dependency on a live repository's
write methods, and only `SimulationRunRepository` can persist. An import-boundary test enforces
this, and an integration test hashes every live collection before and after a run.

## 6. Cascade graph example

```
AST-TR-A (transformer)
  └─POWERS→ AST-DB-A2 (floor panel)
      ├─POWERS→ RM-A204 ──SERVES→ SES-88012 (EXAM, 58 students)
      ├─POWERS→ RM-A206 ──SERVES→ SES-88044 (PRACTICAL)
      └─POWERS→ AST-SW-A-CORE ──CONNECTS→ AST-AP-A2-01
```

Traversal is breadth-first with a visited set and a depth limit. Everything shown is
derived from stored edges, so an AI cannot invent an impact.

## 7. Seed data

`backend/src/main/resources/db/seed/` holds a deterministic generator with a fixed seed:

| Dataset | Volume |
|---|---|
| Buildings / rooms | 8 buildings, about 80 rooms |
| Assets | About 150, with dependency edges for power and network |
| Users | 7 role accounts, 2nd approver, 2nd manager, 6 technicians, 40 students, 12 faculty |
| Timetable | Two weeks of sessions, with an exam placed for Scenario A |
| Inventory | About 60 items, with a critical part at zero for Scenario C |
| History | 6 months of closed incidents, so analytics and recurring incidents have data |

Scenario reset restores a known state using fixtures that are relative to "now", so a
demo never drifts into the past.
