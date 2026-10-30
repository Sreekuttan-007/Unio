# UNIO — Implementation Plan

**Project:** UNIO, for PS 2: CampusOps
**Stack:** React + TypeScript (Vite, Tailwind), Python FastAPI, MongoDB Atlas, Gemini for the
LLM parts, Median.co APK
**Goal:** a working platform that turns a natural-language report into a validated,
coordinated recovery, with a demo that shows it live.

| Document | Covers |
|---|---|
| Official challenge brief (provided separately) | Requirements M1-M10 and C1-C6; not reproduced in this repository |
| `docs/RBAC_AND_NAVIGATION.md` | Permissions, data scope, per-role workspaces |
| `docs/DATA_MODEL.md` | Collections, schemas, indexes, seed data |
| `docs/ML_SERVICE.md` | Models, training, integration |
| `docs/API_CONTRACT.md` | API conventions and endpoints |
| `docs/DEPLOYMENT.md` | Hosting, environment, Median, demo runbook |
| `docs/ASSUMPTIONS.md` | Assumptions and platform checks |
| `AGENTS.md` | Rules for every coding agent, including Antigravity |

---

## 1. What changed from the original plan

These record the team's agreed scope where it differs from the original proposal.

| Original | Now | Why |
|---|---|---|
| Capacitor wrapper | **Median.co APK** | Team decision. Median wraps the live site |
| Packaging near the end | **Deploy and test the APK in Phase 1** | The APK depends on a live URL, so risks surface early |
| SRM Easwari master layout | **Our own fictional campus SVG** | PS C2 says to generate fictional data |
| Form-led intake | **Form, chat and simulated email** | M1, and email also satisfies C5 |
| Collision Engine after bookings and work orders | **Collision Engine first** | Otherwise both features get rewritten |
| Purchase approvals only | **One framework for purchases, costly repairs and overrides** | M7 |
| Idempotency as a detail | **Foundation built in Phase 2** | C4 is graded |
| Separate frontend-only role checks | **Server-driven workspaces** | Your requirement for role-specific features |
| Unspecified "AI" | **A separate ML service with fallbacks** | C6, and the demo survives an AI outage |
| Timetable implied | **Explicit `timetable_sessions`** | M5 requires affected classes |

**All differentiators ship:** Collision Engine, Cascading Event Intelligence, Synthetic
Reality Engine, Invoice-to-Inventory with OCR, Live Campus Map and the Median APK.

---

## 2. Principles

1. **Stay deployed.** Every phase ends live, and tagged `phase-NN-green`.
2. **Finish vertical slices.** A feature counts only when it works from UI to database.
3. **Backend decides.** Frontend displays permissions, actions and collisions.
4. **AI advises.** Permissions, stock and scheduling stay deterministic.
5. **Safe to repeat.** Every event can arrive twice without harm.
6. **UI stays swappable.** Restyling can't change behaviour.

---

## 3. Stack

| Layer | Choice |
|---|---|
| Frontend | React 19, TypeScript, Vite, React Router, TanStack Query |
| UI | Tailwind v4 mapped to CSS tokens, Lucide icons, Inter (bundled) |
| Mocks and tests | MSW, Vitest, Testing Library |
| Backend | Python 3.12, FastAPI, Pydantic v2, PyMongo async driver, PyJWT, Argon2 |
| Backend tests | pytest, httpx, an in-memory MongoDB mock, optionally a real MongoDB |
| AI and ML | scikit-learn, RapidFuzz and pdfplumber inside the backend (`app/ml`) |
| LLM | Gemini through a provider interface (`google-genai`) |
| Live updates | Polling with TanStack Query, every 5-10 seconds on live screens |

Polling is the deliberate choice over WebSockets: it behaves well in a WebView, needs no
reconnect logic, and looks live in a demo.

---

## 4. Repository

```
overclock-hack/
├── AGENTS.md
├── IMPLEMENTATION_PLAN.md
├── docker-compose.yml, render.yaml, .github/workflows/ci.yml
├── docs/
├── frontend/
│   ├── public/{brand,campus}/
│   └── src/
│       ├── app/                 providers and routes
│       ├── platform/            FROZEN: api client, auth, theme, workspace router and registry
│       ├── ui/                  presentation only, props in and markup out
│       ├── features/            containers and data hooks
│       │   └── workspaces/<role>/   one chunk per role
│       ├── mocks/               MSW handlers, plus fixtures generated from the backend
│       ├── styles/tokens.css    every design value
│       └── types/               generated OpenAPI types
└── backend/
    ├── app/
    │   ├── core/                access, scope, permission, state machine, idempotency, outbox
    │   ├── users/  audit/  system/
    │   └── (added per phase) campus/ intake/ incidents/ bookings/ workorders/ collision/
    │       cascading/ simulation/ inventory/ approvals/ invoices/ sla/ notifications/
    │       integrations/ analytics/ ml/ demo/
    ├── tests/
    ├── tools/contract.py        exports the frontend contract
    └── dev_server.py            in-memory dev server
```

---

## 5. Cross-cutting designs

### 5.1 Role-specific workspaces

Full design: `docs/RBAC_AND_NAVIGATION.md`.

`GET /me/bootstrap` returns the role's navigation, and only those routes are mounted.
Screen chunks load lazily, so other roles' screens aren't even downloaded. Sidebars map
over an array and contain no role conditions, so features can't get mixed together.

### 5.2 UI tuning alongside feature work

This setup lets Antigravity tune the UI while backend work continues:

| Mechanism | Benefit |
|---|---|
| `ui/` takes props only | Restyling can't touch data or permissions |
| `styles/tokens.css` | Rebrand the whole app from one file |
| Per-role accent token | Each workspace gets its own identity |
| `/dev/ui` gallery | See every component and state without running workflows |
| `npm run dev:mock` | Tune screens with the backend off |
| `availableActions` from the API | Buttons can change shape, never permission |
| Stable `data-testid` values | Layout changes don't break E2E tests |
| Vercel branch previews | Review tuning on a phone by URL |
| Median loads the live site | Merged UI work reaches the APK with no rebuild |

**Branching:** UI work uses `ui/<screen>` branches and touches `frontend/src/ui`,
`frontend/src/styles` and layout in `features/`. Feature work uses `phase/NN-name`.
Merge small and often. A screen file has one owner at a time.

**Every screen ships with five states** in the gallery: loading, empty, error,
permission-denied and populated.

### 5.3 Repeated events (C4)

| Event repeated | Protection | Result |
|---|---|---|
| Double-tap submit | `Idempotency-Key`, plus button disabled while pending | Same response |
| Network retry of a POST | `idempotency_keys` | Same response |
| Same email redelivered | Unique `messageId` | Ignored |
| Same webhook redelivered | Unique `{source, eventId}` | `200`, no reprocessing |
| Same transition sent twice | Compare-and-set on `version` and `status` | Second is a no-op or `409` |
| Same stock posting | Unique `postingKey` | No second movement |
| Same approval decided twice | Status guard | Second is rejected |
| Same escalation | Unique `{slaInstanceId, level}` | Fires once |
| Same notification | Unique `dedupeKey` | One notification |
| Concurrent bookings | Unique slot claims | Exactly one wins |

State machines live in one `StateMachine<S, E>` class per aggregate. Illegal transitions
return `422` and produce an audit entry. Show the Scenario B duplicate webhook replay
to judges: a visible "replay event" button that changes nothing proves C4 live.

### 5.4 Collision Engine

```
CollisionEngine.evaluate(ProposedAction, StateReader) -> CollisionResult

Rules, each a small class:
 RoomOverlapRule, RoomClosedRule, RoomCapacityRule, RoomTypeRule
 TechSkillRule, TechShiftRule, TechAvailabilityRule, TechOverlapRule, TechWorkloadRule
 StockAvailableRule, DuplicateReservationRule
 AssetDowntimeRule, DependencyOrderRule
 SelfApprovalRule, ApprovalLimitRule, SeparationOfDutiesRule, StaleStateRule
```

`StateReader` has two implementations: live and snapshot. The simulator therefore runs
the **same rules** as production against read-only state.

| Decision | Meaning |
|---|---|
| `ALLOW` | No findings |
| `WARN` | Soft finding, acknowledged by the user |
| `REQUIRE_APPROVAL` | Needs an override approval with a reason |
| `BLOCK` | Hard finding, cannot proceed |

Every action is checked twice: on preview for the explanation, and at commit, where the
slot claim or conditional update makes the result final. That is M7's "revalidated
before execution".

### 5.5 Audit and outbox

Business changes write `audit_logs` and `outbox_events`. A dispatcher turns outbox
events into notifications and webhooks, with retries. Business code never calls
notification or webhook code directly.

---

## 6. Phases

Size is relative: S, M, L, XL. Convert to dates once the deadline and team size are set.
Each gate requires the deployed app to pass, and `permission-matrix.csv` to be updated.

---

### Phase 0: Lock the contract (S)

**Goal:** agree what is being built before writing code.

- Run `git init` inside `overclock-hack`, and confirm `git rev-parse --show-toplevel`
  prints this folder. The enclosing repo is the whole home directory, so committing from
  there risks exposing personal files and credentials.
- Add a `.gitignore` covering `.env*`, `node_modules/`, `target/`, `dist/` and `ml/data/`.
- Record the agreed product scope in the project documentation.
- Resolve open questions against the official challenge brief supplied by the team.
- Choose the fictional campus: name, 8 buildings, departments.
- Write the four demo scripts as step lists.
- Assign owners: frontend, backend, ML and UI tuning.
- Sketch the campus map and the seven role home screens.

**Gate:** every M and C has an owner, and the deadline is known.

---

### Phase 1: Walking skeleton, deployed (M)

**Goal:** prove the whole delivery chain with almost no features.

**Status: built and verified locally. Four items need your accounts and a phone** (below).

**Built:**
- Backend: FastAPI app factory, MongoDB connection and indexes, health endpoint
  (`/api/v1/system/ping`), one error shape, correlation ids, OpenAPI, Dockerfile.
- Frontend: Vite, Tailwind with `tokens.css`, API client, MSW mocks, app shell, `/dev/ui` gallery,
  Vercel config.
- DevOps: CI workflow, `.env.example` files, `docker-compose.yml`, `render.yaml`.
- Contract tooling: `python -m tools.contract` exports the OpenAPI schema and mock fixtures from
  the backend, and `npm run gen:api` turns the schema into TypeScript types.
- AI and ML now live inside the backend (`app/ml`), so there is no separate ML service to deploy.

**Needs you (cannot be done from here):**
1. Deploy the backend to Render and the frontend to Vercel, and set the environment variables
   in `docs/DEPLOYMENT.md`. The Dockerfile and `render.yaml` have never been run.
2. Run the backend tests once against a real MongoDB (`MONGODB_TEST_URI`), because the default
   run uses an in-memory mock that cannot prove unique-index behaviour.
3. Create the Median app and confirm your plan exports an APK.
4. On a real phone: sign in, kill the app, reopen, and check the session survives.

**Gate:** a phone running the APK shows data from Atlas via the deployed backend. All platform
checks have recorded results in `docs/ASSUMPTIONS.md`.

---

### Phase 2: Identity, RBAC and foundations (L) — M10, C4

**Goal:** seven roles, seven workspaces, and the safety kernel.

**Status: built and tested. 241 backend tests and 46 frontend tests pass.**

**Backend:**
- Users, roles stored in the database, JWT sign-in and server-side sign-out, the `Permission`
  list, `require(...)` guards on a `GuardedRouter`, and a boot-time audit that refuses an open route.
- `scope_filter` data scopes that fail closed, `navigation_for` and `/me/bootstrap`, `/me/badges`.
- `StateMachine` with compare-and-set updates, an idempotency middleware, `AuditService`, and an
  outbox with retries and a dead-letter state.
- `ActionResolver` for server-driven `availableActions`, with reasons.
- Login rate limiting, a decoy hash so unknown emails cost the same as wrong passwords, security headers.
- Admin: users, roles and permissions (with the separation-of-duties rule), audit log.

**Frontend:**
- Login with one-tap demo chips, and a "waking the server" notice.
- A router that mounts only the routes the server names, one code chunk per role.
- Seven workspaces with their own accents. Every navigation key has a screen. Users, Roles and
  Audit are real, and the rest are honest placeholders that name their phase and requirements.
- Loading, empty, error, not-permitted, offline and waking states.

**Tests:** the permission matrix across all seven roles, a route-coverage test, scope filters,
idempotency (including six simultaneous duplicates), state-machine and outbox behaviour, the
frontend contract, role-by-role sign-in, and a test proving a Technician never loads the
procurement or system code.

**Gate met locally:** each role lands on a different app, and a Technician calling a procurement
API gets `403`. Repeat it on the phone once deployed.

---

### Phase 3: Campus data, seed and map (M) — M3, C1, C2

**Goal:** a believable fictional campus.

**Backend:** departments, buildings, floors, rooms, assets, `dependency_edges`,
`maintenance_history`, timetable, student groups, staff and shifts, read APIs, and the
deterministic seed generator.

**Map**
- Build `unio-campus.svg` by hand or in Figma, with a stable `id` per region.
- Bind regions to documents through `campus_map`.
- `CampusMap` in `ui/`: pan, zoom, region states from props, keyboard focus, labels and
  icons in addition to colour.
- Public and operational overlay endpoints.

**Frontend:** campus directory, map screens, Department Resources.

**Gate:** tapping a building on the phone opens live data for it, and the seed reproduces
identically.

---

### Phase 4: Intake and incidents with ML v1 (XL) — M1, M2, C5

**Goal:** the core promise, from report to structured incident.

**ML:** triage, extraction, embeddings, similarity, summary with template fallback.

**Backend**
- `reports`, `ai_suggestions`, `incidents`, `incident_relations`.
- `MlClient` with circuit breaker and fallbacks.
- Priority policy table.
- Duplicate gating and dependency correlation.
- Incident state machine, link and split.
- Chat intake with `conversations`.
- **Simulated email:** a `POST /inbox/simulate` test sender, a poller, the unique
  `messageId` guard, auto-clarification replies, and thread continuation through
  `inReplyTo`.

**Frontend**
- `ReportIssueScreen`: free text first, then review of extracted fields.
- Chat intake and clarification.
- My Reports with timeline and summary.
- Intake Inbox and a "send test email" composer.
- Triage queue with duplicate clusters.

**Tests:** all three channels produce the same structure, the same email twice creates
one report, ML offline still works, prompt-injection text changes nothing.

**Gate:** 10 Wi-Fi reports across form, chat and email merge into one incident with a
summary, and every reporter is preserved. Repeat with ML switched off.

---

### Phase 5: Collision Engine (L) — M4, M5, M7, C6

**Goal:** one tested validator before anything depends on it.

- `ProposedAction` types, `StateReader`, all rules from §5.4.
- `collision_rules`, `collision_checks`.
- `POST /collisions/check`.
- `AlternativeSuggestionService`.
- Collision Review screen and a reusable `CollisionPanel`.
- Rule toggles under Operational Rules.

**Tests:** one unit test per rule, covering allow, soft and hard, plus aggregation.

**Gate:** the matrix from §7 passes, and each finding reads as a clear sentence.

---

### Phase 6: Room bookings (M) — M5

**Goal:** bookings that can't double-book.

- Availability query, slot claims, cancel and reschedule.
- Sessions, closures and maintenance also claim slots.
- Alternatives ranked by capacity, room type, features and distance.
- `GET /timetable/affected` for affected classes.
- Book a Room, My Bookings, Department Bookings.

**Tests:** 20 concurrent requests for one room produce exactly one booking.

**Gate:** a conflicting booking shows the reason, the affected class and alternatives,
and confirming one revalidates it.

---

### Phase 7: Work orders and reassignment (L) — M4

**Goal:** the right technician, including when things change.

- Work-order state machine: `CREATED`, `PENDING_ASSIGNMENT`, `ASSIGNED`, `ACCEPTED`,
  `IN_PROGRESS`, `BLOCKED`, `RESUMED`, `COMPLETED`, `VERIFIED`, `CLOSED`.
- Candidate filter by skills and shift, then an explainable score:

  | Factor | Basis |
  |---|---|
  | Skill level | Above the minimum |
  | Workload | Open task minutes |
  | Priority fit | Preempting lower-priority work |
  | Availability margin | Time left in shift |
  | Proximity | Same or nearby building |

- **Event-driven reassignment:** when a technician becomes unavailable, a task runs late,
  or a higher-priority job appears, `ReassignmentService` recomputes candidates, flags
  affected work orders, and proposes a move.
- Technician screens: My Tasks, accept, decline, block, complete with camera evidence,
  Availability.
- Facilities screens: kanban, assignment panel, Technician Board.
- `maintenance_history` on completion.

**Tests:** double assignment race, sick technician triggers reassignment, Technician
sees only their tasks, blocked work can't be completed.

**Gate:** mark a technician sick on the phone, and Facilities sees affected work with a
ranked replacement.

---

### Phase 8: Cascading Event Intelligence (M) — M5

**Goal:** a traceable answer to "what does this break?"

- Traversal over `dependency_edges`, with cycle protection and a depth limit.
- Rank by directness, exams first, headcount, SLA and asset criticality.
- `impact_snapshots`, recomputed when incident state changes.
- Targeted recipient resolution: only affected people.
- Impact Chain view, map impact zones, Academic Impact for Faculty.

**Tests:** cycles terminate, known fixtures give exact results, no invented entities.

**Gate:** a transformer fault shows the chain to rooms, an exam and its students, and the
map lights up.

---

### Phase 9: Synthetic Reality Engine (L)

**Goal:** compare recovery plans safely before acting.

- `SnapshotReader` with a version and hash.
- Rule-based plan generator: alternative rooms, technicians, repair now or in a window,
  stock or procure.
- Metrics computed only from stored data: rooms affected, people moved, SLA margin,
  parts used and staff minutes.
- Plans run through the same Collision Engine.
- LLM may narrate trade-offs, with numbers supplied by Python code.
- Execute: check for changes since the snapshot, re-run rules on live data, apply through
  normal services, or mark `STALE` and ask for a re-run.

**Frontend:** scenario setup, plan comparison, conflict indicators, execute result.

**Tests:** hash of live collections unchanged after simulating, an import-boundary
test, a stale plan refused after a live change.

**Gate:** Plan A is blocked with a reason, Plan B is valid, and changing live data between
simulation and execution triggers `STALE`.

---

### Phase 10: Inventory, approvals, Invoice-to-Inventory (XL) — M6, M7

**Goal:** the complete missing-part path.

**Inventory:** balances, conditional reservation, ledger, reorder alerts, `BLOCKED`
status on shortage.

**Approvals:** the `approvals` framework for all three types, `approval_rules` matrix,
self-approval and limit rules, clarification loop, and revalidation at execution.

**Procurement:** purchase orders and fictional suppliers.

**Invoice-to-Inventory:**
1. Upload a file to object storage.
2. Extract with the ML service.
3. Review fields beside the document.
4. Match against the PO with deterministic rules.
5. Resolve discrepancies.
6. Validate the goods receipt.
7. Post the ledger once.
8. Allocate to the reservation and resume the work order.

**Frontend:** Approval Queue, Requests, Orders, Invoices, Discrepancies, Goods Receipts,
Inventory, My Parts.

**Tests:** invoice upload changes no stock, replayed receipt posts once, stock can't go
negative, 20 concurrent reservations never oversell, self-approval fails, System
Administrator can't approve, stale approval is refused.

**Gate:** a zero-stock part travels from Technician to approved purchase, invoice,
receipt and resumed work, with one ledger entry.

---

### Phase 11: SLA, notifications, webhooks, analytics (L) — M8, M9, C5

**SLA:** policy lookup, deadlines, pause and resume, sweep job plus compute-on-read,
escalation ladder, SLA risk from ML shown as a separate signal.

**Notifications:** in-app centre, bell badge, targeted recipients, deduplication.

**Webhooks:** signed outbound delivery with retries and a delivery log. Add a simulated
receiver page, plus signed inbound events with replay protection.

**Analytics, computed from stored data:**

| Metric | Definition |
|---|---|
| Open requests | By status, category, building and age |
| SLA compliance | Met ÷ closed, by category and priority |
| Utilisation | Booked ÷ available room hours; assigned ÷ shift hours for technicians |
| Shortages | Items below threshold, blocked work, frequency |
| Recurring incidents | Same asset, room or category repeating within a window |

**Tests:** SLA boundaries, pause arithmetic, single escalation, webhook signature,
analytics against fixtures with known answers.

**Gate:** an overdue task escalates once, the right people are notified, a webhook is
delivered and logged, and every chart matches its fixture.

---

### Phase 12: Workspace polish with Antigravity (L)

**Goal:** make seven workspaces feel like distinct, finished products.

| Priority | Screen |
|---|---|
| 1 | Facilities Command Centre |
| 2 | Report Issue, including chat |
| 3 | Technician My Tasks |
| 4 | Live Campus Map |
| 5 | What-if Simulator |
| 6 | Procurement Approval Queue and invoice review |
| 7 | Remaining screens |

Rules:
- Review on a 360px phone first, then 1440px.
- Tune tokens before components, and components before screens.
- Replace placeholder content, and keep all labels clear.
- Check contrast, focus states and motion in both themes.
- Do not change hooks, API calls or `platform/`.
- Each screen needs all five states before it is done.

**Gate:** someone new to the project can identify the role of any screenshot, and core
flows pass at phone width.

---

### Phase 13: Harden, Median final, rehearse (L) — C3

- Playwright E2E for all four scenarios.
- Scenario reset screen working in one click.
- Median icon, splash and device checklist.
- Move to always-on hosting.
- Security pass: secrets scan, CORS, upload limits, headers, audit coverage.
- Keep requirement-to-evidence traceability in team notes without reproducing the challenge brief.
- Timed rehearsals, including ML off and network loss.
- Record the backup video.

**Gate:** two clean runs in a row from a fresh reset, on the APK and the desktop.

---

## 7. Collision test matrix

| Case | Expected |
|---|---|
| Same room, overlapping time | `BLOCK ROOM_OVERLAP` |
| Same room, touching end and start | `ALLOW` |
| Room closed or under maintenance | `BLOCK ROOM_CLOSED` |
| Headcount above capacity | `BLOCK ROOM_CAPACITY` |
| Lab session in a plain classroom | `WARN ROOM_TYPE` |
| Technician lacks skill | `BLOCK TECH_SKILL` |
| Outside shift | `WARN TECH_SHIFT` |
| On leave | `BLOCK TECH_UNAVAILABLE` |
| Overlapping assignment | `BLOCK TECH_OVERLAP` |
| Above workload limit | `WARN TECH_WORKLOAD` |
| Stock short | `BLOCK STOCK_SHORT`, work order `BLOCKED` |
| Same part reserved twice for one work order | `BLOCK DUPLICATE_RESERVATION` |
| Asset in maintenance | `BLOCK ASSET_DOWN` |
| Requester approves own request | `BLOCK SELF_APPROVAL` |
| Amount above limit | `REQUIRE_APPROVAL APPROVAL_LIMIT` |
| State changed since preview | `BLOCK STALE_STATE` |
| Soft finding with authorised override | Proceeds, audited |
| Hard finding with override attempt | Still blocked |

---

## 8. Demo scenarios

**Scenario A: Exam room lost.** A panel fault hits the room of a morning exam.
Reports arrive, the cascade finds the exam, booking the obvious room collides, the
simulator compares options, and the chosen move is revalidated. Only those students and
the faculty member are notified.

**Scenario B: Wi-Fi outage.** Reports come in through the app, chat and email. The system
merges them through the shared switch, produces a summary, and shows one incident. A
replayed webhook changes nothing.

**Scenario C: Critical part out of stock.** The Technician flags a missing part and the
work blocks. A purchase request is raised, self-approval is refused, the approver
approves, the invoice mismatch is flagged and resolved, the receipt posts once, and work
resumes.

**Scenario D: Technician unavailable.** A technician marks themselves sick on the APK.
Affected work is flagged, the Collision Engine rejects an unqualified replacement, a
qualified one is assigned, and the SLA stays visible.

Lead with B, then A, because they show the most in the least time. Keep C and D ready for
deeper questions. **Show AI off for 30 seconds:** switching the ML flag off and watching
every workflow continue is direct proof of C6.

---

## 9. Parallel work

| Track | Owns | Depends on |
|---|---|---|
| Backend core | RBAC, workflows, engines | Data model |
| ML | `ml/`, model cards | Frozen `schemas.py` |
| Frontend features | `features/`, MSW fixtures | API contract |
| UI with Antigravity | `ui/`, tokens, layout | Screen states |

Order that avoids blocking:

1. Agree schemas and API contract in Phases 0-2.
2. Frontend builds against MSW while backend builds the real endpoint.
3. ML ships stubs first, then real models behind the same schema.
4. Merge in small PRs, and replace mocks one endpoint at a time.

If you are a small team, follow the phase order. Keep Phases 1-4 strict, because
everything else depends on them.

---

## 10. Antigravity instructions

**Start every session with:**

```text
Read AGENTS.md, IMPLEMENTATION_PLAN.md and the relevant project docs first. Consult the official
challenge brief supplied by the team when a requirement needs clarification.
Inspect the current repo and report its state in one paragraph.
Current task: <phase and exact scope>.
Implement only this scope. List files you will change before editing.
Run the real build and tests. Report actual output, known gaps and the next step.
Do not report success for anything you did not run.
```

**UI tuning prompt:**

```text
Task: tune <screen> for the <role> workspace.
Work only in frontend/src/ui, frontend/src/styles and layout in frontend/src/features.
Do not change hooks, API calls, routing, permissions or frontend/src/platform.
Use design tokens only. Keep data-testid values.
Run with npm run dev:mock.
Cover loading, empty, error, not-permitted and populated states.
Check 360px and 1440px, in light and dark.
Run lint, typecheck and tests, and report real results.
```

---

## 11. Traceability

| Req | Built in | Proved by |
|---|---|---|
| M1 | P4 | Three-channel intake |
| M2 | P4 | Scenario B |
| M3 | P3 | Campus directory and map |
| M4 | P7 | Scenario D |
| M5 | P6, P8 | Scenario A |
| M6 | P10 | Scenario C |
| M7 | P5, P10 | Scenario C, stale approval test |
| M8 | P11 | SLA Monitor, escalation |
| M9 | P11 | Analytics screens |
| M10 | P2 | Permission matrix, self-approval test |
| C1 | P1 | MongoDB Atlas |
| C2 | P3 | Seed generator |
| C3 | P13 | Four scenarios |
| C4 | P2 onward | Replay and concurrency tests |
| C5 | P4, P11 | Simulated inbox, signed webhooks |
| C6 | P4, P5 | ML-off demo |

---

## 12. Top risks

| Risk | Mitigation |
|---|---|
| Scope is very large for the time available | Each tag is demoable, Phases 1-4 are strict, and agree dates at Phase 0 |
| Free hosting sleeps or runs out of memory | Measure in Phase 1, use always-on hosting before judging |
| Median plan can't export an APK | Confirmed in Phase 1 |
| Atlas transactions unavailable | Guarantees rely on atomic writes and unique indexes |
| ML accuracy on real phrasing is weak | Hand-written holdout, human confirmation, rule fallback |
| AI API blocked or unavailable | Fallbacks are tested, and the ML-off demo becomes a strength |
| Frontend and backend drift | Generated types, with a CI check |
| Dirty demo data | One-click reset |
