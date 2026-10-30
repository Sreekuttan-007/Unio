# Handoff: UNIO build, Phases 7 to 13 done in code

Updated 2026-10-30. Read `AGENTS.md` first. This handoff travels with the source.

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

### A. Database (do first: everything else depends on it)

The app runs on real MongoDB (`MONGODB_URI`, `MONGODB_DATABASE`; `docker compose up --build` starts one locally), but every test so far ran on **mongomock**, an in-memory imitation. mongomock cannot prove that unique indexes stop concurrent writes, which is what the race protections rely on.

1. Start MongoDB (`docker compose up mongo`, or a free Atlas cluster), then run the whole suite against it:
   `MONGODB_TEST_URI=mongodb://localhost:27017 python -m pytest -q`
   Done when: all tests pass, especially `test_twenty_concurrent_reservations_never_oversell`, `test_one_order_assigned_to_two_technicians_at_once_ends_with_exactly_one`, `test_twenty_simultaneous_requests_for_one_room_make_exactly_one_booking`, and the ledger replay tests.
2. Check that `ensure_indexes` in `backend/app/db.py` creates every unique index on a real database (`stock_ledger.postingKey`, `notifications.dedupeKey`, `sla_instances.subjectId`, slot `_id`s). Done when: `db.<collection>.getIndexes()` lists them.
3. Create the hosted database (MongoDB Atlas) and set `MONGODB_URI` in Render. Done when: `GET /api/v1/system/ping` on the deployed API says `"database": "UP"`.
4. Startup reconciler on real data: stop the API in the middle of a goods-receipt validation, restart, and confirm `/admin/system/health` shows "Stock ledger fully applied".

### B. Code still missing (can be done without any accounts)

| # | Phase | Task | Where | Done when |
|---|---|---|---|---|
| B1 | 8 | Tell the affected people. Snapshots already hold `recipientUserIds`; enqueue an `impact.changed` outbox event when the set grows, deduplicated per person | `app/cascade/service.py` `refresh()`, text in `app/notify/service.py` `WORDS` | A test: a transformer fault notifies the exam's students and lecturer, nobody else, once |
| B2 | 10 | Reorder alerts: when free stock falls to or below `reorderThreshold`, enqueue `inventory.low` to Procurement, once per item until it recovers | `app/inventory/ledger.py` or `service.py` after reserve/issue | A test: reserving below the threshold notifies once |
| B3 | 10 | Answer a clarification question in the UI (`POST /approvals/{id}/answer` already exists) | `frontend/src/features/approvals/ApprovalsScreen.tsx` | The requester sees the question and a reply box |
| B4 | 9 | More simulator plans: "repair in the next free window", "use stock vs buy"; add an "SLA margin" metric to every plan | `app/simulation/planner.py` | Tests with known answers for each plan |
| B5 | 11 | Webhook management screen: add, edit, disable, view the delivery log (`webhook_deliveries`) | backend routes in `app/notify/router.py`, screen in `features/admin` | Matrix rows plus a test that a disabled hook gets nothing |
| B6 | 13 | Playwright click-through scripts for Scenarios A to D (use `POST /admin/scenarios/{id}/reset`, then drive the UI like `scripts/phone-check.mjs`) | `frontend/scripts/` | Two clean runs in a row |
| B7a | 12 | ~~Repeat `phone-check.mjs` at 1440px and in dark mode~~ Done: the script now takes a width and a `--dark` flag. All four combinations (360/1440 × light/dark) pass against both `dev:mock` and the real backend. Caught and fixed one real bug in the process: the invoice/discrepancy screens overflowed sideways at 1440px (a CSS grid column missing `min-w-0` let the table's intrinsic width push past the viewport instead of scrolling inside its own card). | `frontend/scripts/phone-check.mjs`, `frontend/src/features/procurement/ProcurementScreens.tsx` | Done |
| B7b | 12 | Check every screen has loading, empty, error, offline and no-permission states | manual audit against `frontend/src/ui/states.tsx` | Not done: a 57-screen manual audit, not something `phone-check.mjs` itself can verify |

### C. Needs a person or an account

| # | Task | Who |
|---|---|---|
| C1 | Gemini key in `GEMINI_API_KEY`, then wire AI invoice reading for photos and scanned PDFs (A30) and the ML SLA-risk signal (A35) | Team, with a Google AI key |
| C2 | Approve or reject a public inbound-webhook route (frozen file `core/access.py`, A33) | Human decision |
| C3 | Visual design polish of every workspace (the plan's Antigravity pass) | Designer |
| C4 | Deploy to Render with always-on hosting; build the Median APK with icon and splash; device checklist | Team accounts and an Android phone |
| C5 | Confirm or change assumptions A15 to A36 in `docs/ASSUMPTIONS.md` | Team, against the challenge brief |
| C6 | Timed rehearsals (also with AI off and with the network lost), and the backup video | Team |

## Running it

```bash
# backend (from backend/)
python -m pytest -q
python dev_server.py                      # API on :8000 with demo accounts and in-memory data
python -m tools.contract --check

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
