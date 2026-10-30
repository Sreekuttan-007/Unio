# Handoff: UNIO build, Phases 7 to 13 done in code

Updated 2026-10-30. Read `AGENTS.md` first. This handoff travels with the source.

## Where things stand

- Phases 7 to 12 are complete and each has a green tag: `phase-07-green` to `phase-12-green`. Phase 13 is done for everything that can be done in code (see "Not verified" below).
- Gates on the final commit: backend tests pass (run `pytest -q`), the API contract check passes, frontend typecheck, lint, tests and build pass, and `scripts/phone-check.mjs` opens all 57 screens of the 7 roles at 360px with no sideways scroll, crash or console error, both against `npm run dev:mock` and against the real backend (`dev_server.py`).
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

## Not verified, and why (keep reporting)

- **Median APK, Render hosting, timed rehearsals and the backup video**: these need accounts, devices and people. Nothing here was tested on a phone or a hosted deployment.
- **Real MongoDB concurrency**: tests use mongomock. Set `MONGODB_TEST_URI` to run the race tests (reservations, assignments, slot claims) against a real database.
- **Gemini**: never called. Invoices are read by a deterministic text reader; photos and scanned PDFs arrive with a "nothing read" discrepancy (A30). No ML SLA-risk signal (A35).
- **Inbound webhooks from outside**: not built, because it needs a new public route, which is a frozen-file change (A33).
- **Playwright end-to-end scenario scripts**: the scenarios are covered by API-level tests and the reset tests, and every screen is opened by the phone check, but click-through scripts for each scenario were not written.

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
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173   # needs Playwright installed globally
```

On Windows use `.venv\Scripts\python` instead of `python`.
