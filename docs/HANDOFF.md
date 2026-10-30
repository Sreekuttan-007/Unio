# Handoff: UNIO build, Phase 7 in progress

Written 2026-10-30 for cross-account continuation without the original chat.
Read `AGENTS.md` first. This handoff is project context and should travel with the source.

## Where things stand

- Branch `main` is based on `293d72b` (Phases 1 to 6). This handoff accompanies the in-progress Phase 7 implementation.
- Current checks: backend 831 tests passed, with one pre-existing `RuntimeWarning` in the simultaneous-booking test; frontend typecheck, lint, 46 tests and production build pass; API contract check passes.
- The original challenge brief is supplied separately and is intentionally not copied into this repository.
- Continue Phases 7, 8, 9 and 10 in order (see `IMPLEMENTATION_PLAN.md` section 6). Report honestly, including what is unverified.

## Phase 7 progress (work orders)

| Implemented in this snapshot | Notes |
|---|---|
| `backend/app/workorders/state.py, policy.py, scoring.py, service.py, router.py` | State machine, skill/duration policy, 5-factor explainable score, assignment via `collisions.enforce(ASSIGN_TECHNICIAN)`, technician slot claims, flag/propose reassignment, preemption, availability, maintenance history |
| `backend/app/files/service.py, router.py` | `FileStore` (JSON base64 uploads, size and magic-byte checks), `GET /files/{id}` |
| `backend/app/collision/acknowledge.py` | Shared `Acknowledging` body, bookings router now imports it |
| `backend/app/bookings/slots.py` | `SlotClaims(db, collection, key_field)` generalised, technicians use `technician_slots` |
| `backend/app/incidents/service.py` | `collisions` param, DEP-001 used for resolve, `_apply/advance/note_assignment/note/refresh_impact` |
| `backend/app/collision/reader.py` | `technician_tasks` now also returns priority, buildingId, estimatedMinutes |
| `services.py, main.py, db.py, system/router.py, incidents/router.py, staff/service.py` | Wired, work-order placeholders removed, indexes added, `needsReplacement` on technician cards |
| `backend/tests/permission_matrix.csv` | 18 rows added by `matrix.py` (generates rows from `roles.json`) |

Known to-do inside Phase 7:
1. Write `backend/tests/test_workorders.py`: state machine, double-assignment races (two WOs/one technician and one WO/two technicians), sick-technician reassignment suggestions, technician task scope, blocked-work completion denial, completion notes, preemption, `review_late`, scoring, and incident `createWorkOrder` end to end.
2. Tests need a shift around "now" (`shifts` collection) for in-shift assertions, or use P1 urgent work. Seeded shifts follow real time.
3. Frontend: `AssignPanel` sends `acknowledged/overrideReason` but the backend wants `acknowledgedCodes` plus `overrideReason`. Send the displayed SOFT finding codes. Update `mocks/domainHandlers.ts` to match. Technician completion should send photos as base64 `evidence`. Block sheet needs a part picker (needs `GET /inventory/catalog`, Phase 10). Work order sheet needs verify/reject buttons driven by `availableActions`. `needsReassignment.suggestedName` can now be null.
4. Add `docs/ASSUMPTIONS.md` rows A15 and onwards: policy table for skills and durations, `RESUMED` folded into `RESUME` to `IN_PROGRESS`, `CREATED` folded into `PENDING_ASSIGNMENT`, preemption only flags, reassignment only proposes.
5. Add focused Phase 7 coverage before considering the phase complete.

## Remaining phases (design decisions already made)

- **Phase 8 cascade** `backend/app/cascade/`: pure BFS over `dependency_edges` (visited set, depth limit), sessions derived from `timetable_sessions` by affected room, ranking by directness, exams, headcount, SLA, asset criticality. `impact_snapshots` refreshed through `IncidentService.refresh_impact` (`incidents.cascade = cascade` set in `build_services`; add refresh calls in `_create`, `_join`, `complete_placement`, `_merge`). Endpoints `GET /cascading/impact/{id}`, `POST .../recompute`, plus a faculty-scoped `GET /cascading/academic` (Academic Impact screen currently hardcodes INC-1041). Map overlays should use impact snapshots. Recipients are only the affected people. Seed topology: transformer to panel to room (POWERS), transformer to building switch to floor switch to AP (CONNECTS) to room (SERVES).
- **Phase 9 simulator** `backend/app/simulation/`: `SnapshotReader` implements `StateReader` in memory with version and hash and an `apply()` so later actions see earlier ones. Rule-based plan generator, plans judged by the same `CollisionEngine`, metrics from stored data only, optional LLM narration with numbers supplied by Python. Only write is `simulation_runs`. Execute recomputes a fingerprint of the facts the plan depended on from live data; changed gives `STALE`; otherwise apply through the normal services (`bookings.move_session`, `workorders`, inventory) as the user. Tests: hash of live collections unchanged, import-boundary test, stale plan refused. Frontend `SimulatorScreen` expects `SimulationRun {id, incidentId, snapshotAt, plans[], recommendedPlanId}`.
- **Phase 10** inventory, approvals, procurement, invoices, receipts: shapes the UI expects are in `frontend/src/types/domain.ts` and `mocks/domainHandlers.ts` (`/inventory/items`, `/inventory/mine`, `/approvals`, `/approvals/{id}/decide`, `/purchase-orders`, `/invoices`, `/invoices/{id}/resolve|validate`, `/goods-receipts`, `/goods-receipts/{id}/validate`). Conditional `$inc` reservation, immutable ledger with unique `postingKey` and a startup reconciler, approvals routed by amount (`approval_rules`), self-approval and limits via the collision rules already in `collision/rules.py`, revalidation at execution (`STALE`), invoice upload never moves stock, only a validated goods receipt posts, receipt verifier must differ from approval requester and receiver, then reserve and resume the blocked work order and release the SLA pause. `WorkOrderService.inventory` is the hook (`request_parts`, `issue_for_completion`, `release_for_work_order`). `pypdf` was pip-installed (add to `requirements.txt`). Gemini invoice extraction needs a fallback text parser. Remove the remaining 501 placeholders in `app/system/router.py` as each lands.

## Rules and habits that matter

- Frozen files need an explicit human yes (list in `AGENTS.md` section 4). No new permissions are needed for Phases 7 to 10; the ones required already exist in `core/permission.py`.
- Every route needs `require(...)` or `authenticated` and a row in `permission_matrix.csv` (`scratchpad/matrix.py` style generator, or add rows by hand using `x` for path params).
- Shell: Bash heredocs break on apostrophes in this environment. Write files with the editor/Write tool, or put a patch script in a file and run it.
- Validation errors are HTTP 400, domain rule errors 422, version conflicts 409, out-of-scope rows 404.
- Windows blocks scikit-learn; ML here is pure Python.
- Tests use mongomock, which cannot prove real unique-index concurrency. Set `MONGODB_TEST_URI` to test on real MongoDB.
- Gate before reporting done: backend `.venv/Scripts/python -m pytest -q`, frontend `npm run typecheck && npm run lint && npm test`, frontend `npm run build`, and backend `python -m tools.contract --check`.

## Known unverified items (keep reporting)

Gemini live calls, real MongoDB concurrency, Median APK, Docker and `render.yaml`, outbox delivery to notifications (Phase 11), no UI yet for reschedule-booking and move-class.
