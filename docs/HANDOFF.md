# Handoff: UNIO build, Phases 7 to 13 done in code

Updated 2026-10-31. Read `AGENTS.md` first. This handoff travels with the source.

## Where things stand

- Phases 7 to 12 are complete and each has a green tag: `phase-07-green` to `phase-12-green`. Phase 13 is done for the scenario reset and the security pass; what is left is listed under "Remaining work".
- Gates on the final commit: backend tests pass (run `pytest -q`), the API contract check passes, frontend typecheck, lint, tests and build pass, and `scripts/phone-check.mjs` opens all 57 screens of the 7 roles with no sideways scroll, crash or console error, at 360px and 1440px, light and dark, both against `npm run dev:mock` and against the real backend (`dev_server.py`).
- Every phase is one commit on its own branch, stacked: `phase/07-work-orders` → … → `phase/13-harden`.

## What each phase added

| Phase | Backend | Frontend | Tests |
|---|---|---|---|
| 7 Work orders | Fixed: the loser of a concurrent assignment deleted the winner's technician slots | AssignPanel sends `acknowledgedCodes`; photo evidence on completion; verify / send back from `availableActions` | `test_workorders.py` |
| 8 Cascade | `app/cascade/`: pure BFS over `dependency_edges`, `impact_snapshots`, `impactRoomIds` used by bookings, map overlays from snapshots, recompute with root assets, faculty-scoped academic view | Command Centre and Academic Impact use real incidents (no hard-coded INC-1041) | `test_cascade.py` |
| 9 Simulator | `app/simulation/`: in-memory `SnapshotReader` (the live reader over a copy), three rule-based plans judged by the collision engine, fingerprint-checked execution through the normal services, `STALE` | Simulator defaults to a real open incident | `test_simulation.py` (live hash unchanged, import boundary, stale refused) |
| 10 Inventory | `app/inventory/` (CAS reservations, ledger with unique `postingKey` and reconciler), `app/approvals/` (routing table, collision rules, STALE), `app/procurement/` (POs, invoice reader and matching, goods receipts) | Part picker on the blocker sheet; invoice upload sends the file | `test_inventory.py` (the full missing-part gate, 20 concurrent reservations) |
| 11 SLA and notify | `app/notify/` (notifications and signed webhooks as outbox handlers), `app/sla/board.py` (lists, summary, escalation sweep), `app/analytics/` | Notification bell and centre; navigation badges | `test_notify.py` (analytics fixture with known answers) |
| 12 Polish | `session.move` offered in impact views | Reschedule a booking; move an affected class from triage; `.env.mock` committed so mock mode works on a fresh clone; analytics key fix | `scripts/phone-check.mjs` |
| 13 Harden | `app/scenarios/`: one-click reset of Scenarios A to D (demo mode only, audit kept) | Admin Scenarios screen now real | `test_scenarios.py` |

All new business rules are listed in `docs/ASSUMPTIONS.md` (A15 to A36).

## Honest status

The core of every phase from 7 to 13 is built and tested. These items from `IMPLEMENTATION_PLAN.md` are **not** done yet. Phases 0 to 6 were built before this handoff and were not re-audited against the plan.

## Remaining work, in the order to do it

Each task says where the code goes and what proves it is done. Keep the habits from `AGENTS.md`: one branch per phase, full test suite green before each commit, a row in `permission_matrix.csv` for every new route.

### A. Database — done, against a real MongoDB Atlas cluster

**This is no longer a TODO.** The app runs, right now, against a real hosted MongoDB Atlas
database, not mongomock and not `dev_server.py`'s in-memory copy. What that means concretely:

- **Cluster**: `UNIO-CampusOps-Atlas` on Atlas, database name `unio_live`. Connection string is in
  the local, gitignored `backend/.env` (`MONGODB_URI`, `MONGODB_DATABASE`) — never committed, and
  the database user's password has been rotated at least once already after being pasted in a
  chat session, which is worth doing again before this goes in front of anyone external
  (Atlas → Database Access → the user → Edit Password → Autogenerate).
- **Run it** with the real factory entrypoint (same one `Dockerfile`/Render use), not
  `dev_server.py`:
  `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
  `dev_server.py` still exists and is still useful (it's the one thing `scripts/scenario-check.mjs`
  needs, since a scenario reset is a real destructive write and dev_server's data is disposable),
  but it is no longer how this app is actually run.
- **Demo mode, deliberately split in two.** `DEMO_MODE_ENABLED=true` turns on the 7 one-tap
  login tiles (plus 7 secondary actors used by the scenarios) — convenient, and safe against a
  real database because it only ever inserts fixed demo accounts, never overwrites anything.
  `SEED_CAMPUS=true` is the separate, bigger decision: it generates the full fictional-position
  campus (buildings, rooms, assets, timetable, inventory). Turn it off
  (`DEMO_MODE_ENABLED=true`, `SEED_CAMPUS=false`) for one-tap logins against an otherwise empty,
  real campus you build yourself through the Admin screens.
- **Every documented concurrency guarantee was checked against real index metadata in Atlas**,
  not just read in the code — `db.<collection>.getIndexes()` was actually run. Two things this
  caught:
  - `room_slots`/`technician_slots`/`sla_escalations` looked index-less at first glance but are
    fine: their uniqueness is the document's own `_id` (`{roomId}|{slotStart}`,
    `{slaInstanceId}:{level}`), which Mongo always indexes by default. No separate index needed.
  - **`invoices` genuinely had no protection at all** — `docs/DATA_MODEL.md` documents a unique
    index on `{supplierId, invoiceNumber}` that was never created, and the collection's `_id` is
    a plain sequential counter, not derived from those fields. The same invoice could be uploaded
    twice with nothing stopping it. Fixed: `app/db.py` now creates that index (partial, so an
    invoice extraction that couldn't read a supplier/number doesn't collide with every other one
    that also couldn't), `app/procurement/service.py` turns the resulting `DuplicateKeyError`
    into a real `409 DUPLICATE_INVOICE`, and there's a test for it. Applied to the live database
    directly, not just the next restart.
- **Every collection is populated**, through the real service layer (incident submission, work
  order assignment, approval decisions, invoice matching, goods-receipt validation, bookings,
  a simulation run) — never a raw document insert, so every reference is valid and every side
  effect (notifications sent, SLA clocks started, audit trail written) actually happened. The one
  collection still empty, `idempotency_keys`, is supposed to be: it's a 24-hour replay cache that
  only gets an entry when a real client retries a POST with an `Idempotency-Key` header.
- **Campus is rebranded** to the real SRM Easwari Engineering College — see the new section below.

**Still genuinely open, the one real item left from the original list:**

4. Startup reconciler on real data: stop the API in the middle of a goods-receipt validation,
   restart, and confirm `/admin/system/health` shows "Stock ledger fully applied". Not attempted —
   would need an intentionally-interrupted write against the live database to prove.

The test suite itself (`pytest -q`) still runs on **mongomock** by design, and that's fine — it's
not a gap. mongomock is fast (1160 tests in ~2.5 minutes) and every one of the uniqueness/CAS
guarantees it's meant to prove has now separately been confirmed against the real database's
actual index metadata, which is the thing that was actually missing before, not a full real-DB
test run. `MONGODB_TEST_URI` still exists as an option in `tests/conftest.py` if a full real-DB
test run is ever wanted instead.

### B. Code still missing (can be done without any accounts)

| # | Phase | Task | Where | Done when |
|---|---|---|---|---|
| B1 | 8 | ~~Tell the affected people~~ Done: `CascadeService.refresh()` diffs the previous snapshot's `recipientUserIds` against the new one and enqueues `impact.changed` only for people newly added, so a refresh that adds nobody new notifies nobody again. | `app/cascade/service.py` `refresh()` | Done |
| B2 | 10 | ~~Reorder alerts~~ Done: `_check_reorder()` runs after every reserve, release and goods receipt; a CAS flag on the item (`lowStockAlertSent`) means crossing the threshold tells Procurement exactly once, and it can fire again only after recovering above the threshold first. | `app/inventory/service.py` `_check_reorder()` | Done |
| B3 | 10 | ~~Answer a clarification question in the UI~~ Done: the Detail panel shows the asked question and an answer box when the viewer is the request's own requester and it needs clarification, detected from the same `availableActions`/`unavailableActions` signal the server already sends. | `frontend/src/features/approvals/ApprovalsScreen.tsx` | Done |
| B4 | 9 | ~~More simulator plans~~ Done: Plan D ("repair in the next free window") waits for a technician's real in-shift slot instead of forcing an immediate assignment; Plan E ("use stock, or raise a purchase") checks each short part through the same `RESERVE_PARTS` rule a live request uses. Every plan (A-E) also reports the incident's own SLA margin. | `app/simulation/planner.py` | Done |
| B5 | 11 | ~~Webhook management screen~~ Done: add/edit/enable-disable a webhook, a delivery log, and a replay button that proves the redelivery-safety guarantee live (the dedup key means a replay changes nothing). | `app/notify/router.py`, `app/notify/service.py`, `frontend/src/features/admin/AdminScreens.tsx` | Done |
| B6 | 13 | ~~Playwright click-through scripts for Scenarios A to D~~ Done: `scenario-check.mjs` resets each scenario through the real Admin > Seed screen (not a raw API call, so the reset itself is UI-tested too), then drives the UI the way a judge would and checks the staged story is actually visible - the incident and a simulator run for A, the waiting email and a two-send webhook replay for B, the approval queue and resulting purchase order for C, and the reassignment flag on both the technician's and Facilities' screens for D. Two runs in a row both passed cleanly, against `dev_server.py`. | `frontend/scripts/scenario-check.mjs` | Done |
| B7a | 12 | ~~Repeat `phone-check.mjs` at 1440px and in dark mode~~ Done: the script now takes a width and a `--dark` flag. All four combinations (360/1440 × light/dark) pass against both `dev:mock` and the real backend. Caught and fixed one real bug in the process: the invoice/discrepancy screens overflowed sideways at 1440px (a CSS grid column missing `min-w-0` let the table's intrinsic width push past the viewport instead of scrolling inside its own card). | `frontend/scripts/phone-check.mjs`, `frontend/src/features/procurement/ProcurementScreens.tsx` | Done |
| B7b | 12 | Check every screen has loading, empty, error, offline and no-permission states | manual audit against `frontend/src/ui/states.tsx` | Not done: a 57-screen manual audit, not something `phone-check.mjs` itself can verify |

### C. Needs a person or an account

| # | Task | Who |
|---|---|---|
| C1 | Gemini key in `GEMINI_API_KEY`, then wire AI invoice reading for photos and scanned PDFs (A30) and the ML SLA-risk signal (A35) | Team, with a Google AI key |
| C2 | Approve or reject a public inbound-webhook route (frozen file `core/access.py`, A33) | Human decision |
| C3 | Visual design polish of every workspace (the plan's Antigravity pass) | Designer |
| C4 | Deploy to Render with always-on hosting; build the Median APK with icon and splash; device checklist. The database half of this is already done (section A) — Render just needs the same `MONGODB_URI` set as an environment variable. | Team accounts and an Android phone |
| C5 | Confirm or change assumptions A15 to A36 in `docs/ASSUMPTIONS.md` | Team, against the challenge brief |
| C6 | Timed rehearsals (also with AI off and with the network lost), and the backup video | Team |

### D. Not in the original plan, done since

| # | What | Where | Notes |
|---|---|---|---|
| D1 | Campus rebranded to the real SRM Easwari Engineering College (EEC), from its AICTE mandatory-disclosure filing and a supplied campus SVG | `app/campus/layout.py` (rebuilt from the real map), `app/campus/seed.py`, `app/users/seed.py`, `app/staff/service.py`, `app/ml/extraction.py` | The eight buildings this app has operational data for kept their original `_id`/`code` (`B-ARB`/`ARB` etc.) — every room code, asset id and dependency edge derives from `code`, and the test suite references those as literal strings. Only each one's display name and its real position/shape on the map changed. `CampusMap.tsx` gained path-shaped regions (real footprints aren't all rectangles) alongside the original rects. Department list gained the real EEC academic departments (21 total), purely additively. See A42 in `docs/ASSUMPTIONS.md` for the full detail, including the ML-gazetteer alias fix this needed. |
| D2 | Real drag-and-drop on every file upload | `frontend/src/ui/Dropzone.tsx` | It was a styled label around a hidden file input with no drag handlers at all, despite the name. Now has visual drop feedback; used by issue photos, work-order completion photos and invoice upload through the one shared component. |
| D3 | Invoice duplicate-upload protection actually enforced | `app/db.py`, `app/procurement/service.py` | See section A above — a real, pre-existing gap found while verifying the database, not something introduced by D1/D2. |

## Running it

```bash
# backend (from backend/)
python -m pytest -q
python -m tools.contract --check
python -m ruff check app tests tools      # blocking; python -m mypy app is advisory, see pyproject.toml

# API on :8000, against whatever database backend/.env points at (real Atlas if MONGODB_URI is
# set there - this is how the app actually runs now, including in Docker/Render):
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

# API on :8000 with demo accounts and in-memory data instead - disposable, resets on restart.
# Needed for scenario-check.mjs, since a scenario reset is a real destructive write:
python dev_server.py

# frontend (from frontend/)
npm run typecheck && npm run lint && npm test && npm run build
npm run dev                               # http://localhost:5173 against the backend
npm run dev:mock                          # no backend needed
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173              # 360px light, needs Playwright installed globally
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173 1440         # 1440px light
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173 360 --dark   # 360px dark
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173 1440 --dark  # 1440px dark
```

On Windows use `.venv\Scripts\python` instead of `python`.
