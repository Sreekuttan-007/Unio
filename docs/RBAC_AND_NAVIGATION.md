# UNIO — RBAC, Data Scope and Per-Role Navigation

Satisfies **M10** (backend-enforced RBAC, no self-approval) and **C6** (permissions
use deterministic logic).

**Goal:** seven roles, seven genuinely different applications, one codebase.
A Technician must never see a procurement link. A Student must never receive a
work-order payload. Enforced in three independent layers, any one of which would be
sufficient alone.

---

## 1. Why the usual approach fails

The common hackathon pattern scatters `user.role === 'ADMIN' && <AdminLink/>` through
a shared sidebar. It produces exactly the problem you described — every role's
features tangled into one component — and it isn't security, because the data still
reaches the browser.

UNIO inverts it: **the backend tells the frontend which application to be.**

```
  Layer 1   Permission keys      backend, per endpoint    Depends(require(...))
  Layer 2   Data scope           backend, per query       scope_filter(user, entity)
  Layer 3   Workspace manifest   server-driven nav        GET /me/bootstrap
```

Layers 1 and 2 are the security. Layer 3 is usability. Saying that distinction out
loud to judges is worth marks, because it proves you know which layer is load-bearing.

---

## 2. Permission keys

Flat `resource.action[.scope]` strings in a frozen `StrEnum`. It is the only list of permissions
that exists: a typo is an `AttributeError` at import time, and a role that lists an unknown key is
ignored with a warning instead of granting anything.

`backend/app/core/permission.py` is **FROZEN, append-only**:

```python
class Permission(StrEnum):
    ISSUE_CREATE = "issue.create"
    WORKORDER_ASSIGN_CAMPUS = "workorder.assign.campus"
    APPROVAL_DECIDE_PURCHASE = "approval.decide.purchase"
    ADMIN_ROLES = "admin.roles"
    # about 70 keys, grouped by feature in the file
```

`GET /api/v1/admin/permissions` serves the full list to the role editor. The OpenAPI contract
carries the keys the frontend needs through the bootstrap response.

**The rule that proves separation of duties:** `SYSTEM_ADMIN` holds every `ADMIN_*`
key and **zero** `APPROVAL_DECIDE_*`, `WORKORDER_ASSIGN_*` or `INVENTORY_TRANSACT`
key. Configuring the approval matrix is not approving. Name the test
`test_system_admin_cannot_approve_anything` and put it on a slide.

---

## 3. Role → permission assignment

Stored in MongoDB (`roles_permissions`), seeded from
`backend/src/main/resources/db/seed/roles.json`, so the System Administrator can
genuinely reconfigure it at runtime — which is itself a demoable feature.

| Capability | STUDENT | FACULTY | DEPT_MANAGER | FACILITIES_ADMIN | PROCUREMENT | TECHNICIAN | SYS_ADMIN |
|---|---|---|---|---|---|---|---|
| `issue.create` | ● | ● | ● | ● | ● | ● | ● |
| `issue.read.*` | own | own | department | campus | — | assigned | — |
| `inbox.read` / `inbox.triage` | | | ● / — | ● / ● | | | ● / — |
| `incident.triage` | | | ● | ● | | | |
| `incident.transition` | | | ● | ● | | partial¹ | |
| `incident.summary.read` | own | own | ● | ● | | assigned | |
| `booking.request` | | ● | ● | ● | | | |
| `booking.read.*` | | own | department | campus | | | |
| `booking.coordinate` | | | | ● | | | |
| `workorder.read.*` | | | department | campus | | assigned | |
| `workorder.assign.*` | | | department | campus | | | |
| `workorder.execute` | | | | | | ● | |
| `workorder.verify` | | | ● | ● | | | |
| `technician.availability.self` | | | | | | ● | |
| `technician.availability.manage` | | | ● | ● | | | |
| `collision.check` | | ●² | ● | ● | ● | | |
| `collision.review` | | | ● | ● | | | |
| `cascade.read` | | ●³ | ● | ● | | | |
| `simulation.run` / `.execute` | | | | ● | | | |
| `inventory.read.*` | | | department | campus | campus | reserved | master |
| `inventory.reserve` | | | ● | ● | | request only⁴ | |
| `inventory.transact` | | | | | ● | | |
| `approval.request.create` | | ●⁵ | ● | ● | | request only⁴ | |
| `approval.decide.purchase` | | | | within limit⁶ | ● | | |
| `approval.decide.repair` | | | within limit⁶ | within limit⁶ | ● | | |
| `approval.decide.override` | | | within limit⁶ | ● | | | |
| `invoice.*` / `receipt.validate` | | | | read only | ● | | |
| `sla.read.*` | own | own | department | campus | procurement | own | system |
| `map.read.*` | public | public | operational | operational | — | public+site | — |
| `analytics.read.*` | | | department | campus | procurement | | system health |
| `audit.read.*` | | | | campus | procurement | | system |
| `admin.*` | | | | | | | ● |

¹ Technician may transition only `ASSIGNED → ACCEPTED → IN_PROGRESS → BLOCKED/COMPLETED`
on work orders assigned to them — enforced by the state machine, not by a permission key.
² Faculty receives collision *explanations* through the booking flow, never an override control.
³ Faculty sees cascading impact only as "sessions of mine that are affected" (M5 affected classes).
⁴ Technician raises a `PartRequirement` or an `ApprovalRequest` draft; a manager commits it.
⁵ Faculty only when `user.flags.procurementRequester == true`.
⁶ Capped by `user.approvalLimit`. Above the cap, escalates to `PROCUREMENT_APPROVER`.
   **Never their own request**, at any limit.

---

## 4. Layer 1 — endpoint access

Every route must declare who may call it, using one of three markers from
`backend/app/core/access.py`:

```python
@router.post("/work-orders/{work_order_id}/assign")
async def assign(
    work_order_id: str,
    user: AuthUser = Depends(require(Permission.WORKORDER_ASSIGN_CAMPUS,
                                     Permission.WORKORDER_ASSIGN_DEPARTMENT)),  # any one of
): ...
```

| Marker | Meaning |
|---|---|
| `Depends(require(a, b))` | The caller must hold at least one of the listed permissions |
| `Depends(authenticated)` | Any signed-in user. Only for endpoints about the caller, such as `/me` |
| `dependencies=[public]` | No sign-in. The route must also be on the `PUBLIC_ROUTES` allowlist |

Three independent safeguards stop a forgotten guard from shipping:

1. **`GuardedRouter` refuses to define a route that declares none of the three.** The app
   fails to start, with the route named in the error.
2. **A boot-time audit of the published OpenAPI schema** rejects any open route that is not on
   the explicit public allowlist, even if someone used a plain router.
3. **Tests**: `test_architecture.py` and the permission matrix, below.

---

## 5. Layer 2 — data scope (the layer most teams skip)

A permission answers *may you call this*. A scope answers *which rows*. `scope_filter()` in
`backend/app/core/scope.py` turns the caller and entity type into a Mongo filter that every list
and detail query must include.

```python
async def list_incidents(user: AuthUser, query: dict) -> list[dict]:
    scoped = {"$and": [scope_filter(user, EntityType.INCIDENT), query]}
    return await db["incidents"].find(scoped).to_list(length=100)   # never a bare find({})
```

| Scope | Filter added |
|---|---|
| `OWN` | The reporter or requester field equals the user. For incidents, the `reporterIds` array contains the user |
| `ASSIGNED` | `assignedTechnicianId` equals the user |
| `DEPARTMENT` | `departmentId` is one of the user's managed departments |
| `CAMPUS` | `campusId` equals the user's campus |
| `PROCUREMENT` | Procurement-domain rows only |
| `SYSTEM` | No row filter, but field-level redaction still applies |

It **fails closed**: a role with no scope for an entity, a department manager who manages no
department, or a scope that has no meaning for that entity all match zero rows.

**Field redaction.** A Student fetching an incident they reported receives
`{id, title, category, status, priority, location, timeline[], slaSummary, summary}`
and *not* `assignedTechnicianId`, `internalNotes`, `costEstimate`, `collisionFindings`,
`approvalTrail`. Implement as three response models, `IncidentPublic`, `IncidentDepartment` and
`IncidentOperational`, not one fat model with nulls.

**Return 404, not 403, for out-of-scope rows.** A 403 confirms the row exists.

---

## 6. Layer 3 — the workspace manifest

### One bootstrap call

`GET /api/v1/me/bootstrap`, called once after login, cached in memory, invalidated on
role change.

```json
{
  "user":  { "id": "u_41", "name": "R. Priya", "avatarInitials": "RP" },
  "role":  { "key": "TECHNICIAN", "label": "Technician", "workspace": "technician" },
  "department": { "id": "d_elec", "name": "Electrical Maintenance" },
  "permissions": ["issue.create", "workorder.read.assigned", "workorder.execute", "..."],
  "scopes": { "WORK_ORDER": "ASSIGNED", "INVENTORY": "RESERVED", "INCIDENT": "ASSIGNED" },
  "navigation": [
    { "key": "tech.tasks",        "label": "My Tasks",     "path": "/w/technician/tasks",
      "icon": "clipboard-check",  "badge": { "source": "workorder.open" } },
    { "key": "tech.parts",        "label": "Parts",        "path": "/w/technician/parts",        "icon": "package" },
    { "key": "tech.availability", "label": "Availability", "path": "/w/technician/availability", "icon": "calendar-clock" },
    { "key": "tech.history",      "label": "History",      "path": "/w/technician/history",      "icon": "history" },
    { "key": "tech.map",          "label": "Site Map",     "path": "/w/technician/map",          "icon": "map-pin" }
  ],
  "featureFlags": { "mlTriage": true, "mlDuplicate": true, "mlSummary": true, "ocr": true, "slaRisk": true },
  "theme": { "accent": "amber" },
  "serverTime": "2026-10-30T06:12:00Z"
}
```

- `navigation` is **computed server-side from the permission set**: `navigation_for()` in
  `backend/app/users/navigation.py` holds one manifest per workspace and keeps only the items
  whose permissions the role holds. Edit a role in the admin screen and the sidebar changes.
- `badge.source` is a key resolved separately via `GET /api/v1/me/badges`, so live
  counts don't force a nav recompute.
- `theme.accent` gives each role a distinct accent. Judges register instantly that the
  Technician app and the Procurement app are different products.
- `featureFlags` lets you kill an ML dependency mid-demo without a redeploy.

### Frontend: the workspace registry

`frontend/src/platform/workspaces/registry.ts` is the only place a screen is declared. It maps
each navigation key to a lazily loaded component, and each **workspace is its own chunk**:

```ts
const loaders = {
  technician: () => import('@/features/workspaces/technician'),
  procurement: () => import('@/features/workspaces/procurement'),
  // ...one per role
}

export const SCREEN_REGISTRY = {
  'tech.tasks': screen('technician', 'tech.tasks'),
  'proc.queue': screen('procurement', 'proc.queue'),
  // ...one entry per navigation key
}
```

`WorkspaceRouter.tsx` mounts a route only for the keys the server put in this user's navigation.
Anything else, including a real screen that belongs to another role, falls through to a
"not part of your workspace" page without loading its code.

**What you can show live:** sign in as a Technician, open the browser Network tab, and
try `/w/procurement/queue`. The procurement chunk is never requested. A frontend test proves it by
asserting that the procurement module is never imported for a technician session. The production
build emits one small chunk per workspace (the technician one is about 1 KB).

Both sides are checked against each other. `registry.test.ts` fails if the backend can send a key
with no screen or the frontend declares a screen the backend never sends, and
`test_frontend_contract.py` checks the same from the backend, including that no workspace module
defines another role's screens.

### Chrome: one shell, role-driven content

```
AppShell (container)
├── TopBar      role label, theme toggle, account menu
├── SideNav     desktop, 1024px and up: maps over bootstrap.navigation
├── BottomNav   phone: up to five items on the bar, the rest under More
└── <WorkspaceRouter/>
```

`SideNav` and `BottomNav` live in `ui/` and are given an array. They contain **zero** role
conditionals. That is the architectural answer to "features mixed up on the same role".

Notifications and Profile live in the top bar for every role, so they are shell controls and
not navigation items. A screen shared by two roles, such as Report Issue, gets one registry key
per role (`student.report`, `faculty.report`).

---

## 7. Per-role navigation manifests

Seven distinct products. Nothing is duplicated unless the capability is genuinely shared.

### STUDENT — accent `sky`
```
Home            my open reports, incidents affecting my block, notices
Report Issue    guided intake wizard — also the mobile FAB
My Reports      list + status timeline + incident summary + feedback on closure
Campus Notices  targeted + public facility notices
Campus Map      public layer only: open / closed / affected facilities
```
Mobile bottom nav: Home · Report · Reports · Map. Primary CTA is camera-first.
This is the role you demo on the phone.

### FACULTY — accent `indigo`
```
Home            today's sessions, my bookings, disruptions hitting my rooms
Report Issue    wizard + academic-impact flag (lecture / practical / exam / event)
Book a Room     availability calendar, conflict explanation, alternative suggestions
My Bookings     upcoming / past / rescheduled
Academic Impact which of MY timetabled sessions are affected by live incidents  (M5)
Campus Map      public + room navigation
```

### DEPARTMENT MANAGER — accent `teal`
```
Overview             department KPIs: open incidents, SLA risk, blocked work, shortages
Department Incidents triage and prioritise within department scope
Work Requests        create / reassign within department authority
Resources            department rooms, labs, assets, staff skills and workload
Room Bookings        department bookings and conflicts
Inventory            department stock, reserved, shortages
Approvals            raise purchase / costly-repair requests; decide within limit
SLA & Escalations    compliance, overdue, escalation history
Analytics            department utilisation and recurring incidents
```

### FACILITIES ADMINISTRATOR — accent `rose`
```
Command Centre     hero screen: live incident board by priority, active disruptions,
                   technician load heatmap, blocked work, SLA risk
Live Campus Map    fictional campus SVG + all operational overlays
Intake Inbox       simulated email channel: unprocessed messages -> incidents   (M1, C5)
Incident Triage    unified queue, duplicate-cluster view, correlate / link / summarise
Work Orders        full lifecycle kanban
Technicians        skills, shifts, availability, workload, assignment panel
Collision Review   every collision decision; pending overrides; override with reason
What-If Simulator  scenario builder, plan comparison, execute-after-revalidate
Inventory          campus stock visibility and reservation coordination
Approvals          costly repairs and overrides within authority
SLA Monitor        at-risk and breached; escalation actions
Analytics          campus-wide operational analytics
Audit Trail        operational decision history
```

### PROCUREMENT APPROVER — accent `violet`
```
Overview        pending value, cycle time, discrepancy count
Approval Queue  hero screen: requests awaiting my decision, with shortage evidence,
                linked work order and incident; inline approve / reject / clarify
Requests        all approval requests, filterable by type and status
Purchase Orders issued orders and receipt state
Invoices        upload + OCR extraction review, document and fields side by side
Discrepancies   invoice vs PO mismatch worklist
Goods Receipts  validate receipt — the ONLY path that posts stock
History         closed cycles and audit
```

### TECHNICIAN — accent `amber`
```
My Tasks      hero screen: prioritised queue, SLA countdown per task,
              accept / start / block / complete, camera evidence capture
Parts         parts reserved for my tasks; report missing part
Availability  my shifts, leave, skills — changing this triggers reassignment  (M4)
History       maintenance I have performed
Site Map      navigation to my assigned location only
```
**Mobile-first, one-handed.** Large targets, camera-first completion evidence.
Design this for the phone and let desktop be the afterthought — the opposite of every
other role. This is the second role you demo on the phone.

### SYSTEM ADMINISTRATOR — accent `slate`
```
System Overview     health, API latency, job status, data-quality warnings
Users               create / deactivate / assign role
Roles & Permissions live permission-matrix editor over roles_permissions
Campus Master Data  buildings, floors, rooms, assets, map region binding
Staff & Skills      technician master data, skills, shifts
Inventory Master    items, categories, thresholds, stock locations
Operational Rules   collision rule toggles, hard/soft classification, thresholds
SLA Policies        targets and escalation ladders per category and priority
AI & Integrations   model versions, confidence thresholds, webhook endpoints,
                    simulated email inbox config, notification channels
Audit Logs          system-wide
Seed & Demo Data    reset demo state
```

**Build `Seed & Demo Data` with one-click "Reset to Scenario A / B / C / D".**
It is the highest-value hour in the entire project. A failed live demo is almost
always a dirty database.

---

## 8. Server-driven actions

Every entity DTO carries what *this* user may do to it *in its current state*:

```json
{
  "id": "WO-104",
  "status": "BLOCKED",
  "blockReason": "WAITING_FOR_PARTS",
  "availableActions": [
    { "key": "workorder.requestReassign", "label": "Request reassignment" },
    { "key": "workorder.addNote",         "label": "Add note" }
  ],
  "unavailableActions": [
    { "key": "workorder.complete", "label": "Complete",
      "reason": "Blocked on parts. Reservation RSV-77 is not yet fulfilled." }
  ]
}
```

Computed by `WorkOrderActionResolver` = permission set ∩ state machine ∩ data scope.

Three wins at once: the UI cannot invent an illegal action; `unavailableActions[].reason`
gives free explainability (a greyed button that says *why* reads as a polished product);
and Antigravity restyling a button row cannot change what is permitted.

---

## 9. The tests that win the RBAC question

All of these exist and run in CI (`backend/tests`, 240+ tests).

| Test file | What it proves |
|---|---|
| `test_permission_matrix.py` + `permission_matrix.csv` | Every role against every endpoint: allowed roles reach it, everyone else gets exactly 403. A second test fails if a route has no row, or a row has no route |
| `test_architecture.py` | A route with no access rule cannot be defined, and the boot audit rejects an open route that is not on the public allowlist |
| `test_separation_of_duties.py` | System Administrator holds no business authority, cannot grant it to itself through the role editor, and cannot lock itself out |
| `test_scope.py` | Each data scope becomes the right database filter, and fails closed when none is configured |
| `test_bootstrap.py` | Every role gets only its own workspace, no two roles share a navigation key, and a role holds every permission its own sidebar needs |
| `test_auth.py` | Wrong password and unknown email look identical, rate limiting, logout revokes a token, deactivating a user or changing a role takes effect on the next request |
| `test_idempotency.py` | A retried write runs once, a reused key with a different body is refused, a failed request does not poison its key, six simultaneous duplicates create one record |
| `test_frontend_contract.py` | The generated API contract and mock fixtures are current, and every navigation key has exactly one frontend screen in the right workspace |

Frontend tests (`npm test`) add: each role signs in and sees exactly its own sidebar and accent,
a Technician who types a procurement URL gets "not part of your workspace", and the procurement and
system screen code is never even imported for that session.

Still to add as the features land: `selfApprovalRejected`, `approvalAboveLimitEscalates`,
`technicianSeesOnlyAssignedWorkOrders`, `deptManagerCannotReadOtherDepartment` (404, not 403) and
`studentIncidentDtoOmitsInternalFields`. Each new endpoint gets a row in `permission_matrix.csv`
in the same change, or the coverage test fails.

---

## 10. Demo accounts

Seed one per role, same password, rendered as **one-tap chips on the login page**.
Nothing burns demo time like typing an email on a phone keyboard.

| Email | Role |
|---|---|
| `student@unio.demo` | STUDENT |
| `faculty@unio.demo` | FACULTY |
| `dept@unio.demo` | DEPARTMENT_MANAGER |
| `facilities@unio.demo` | FACILITIES_ADMIN |
| `procure@unio.demo` | PROCUREMENT_APPROVER |
| `tech@unio.demo` | TECHNICIAN |
| `sysadmin@unio.demo` | SYSTEM_ADMIN |

Also seed a **second** Procurement Approver, a **second** Department Manager and
**four** Technicians with different skill sets. You cannot demonstrate self-approval
prevention, approval escalation, or a technician scheduling collision with one of each.
