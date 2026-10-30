# UNIO — Assumptions Log

Anything not stated in `docs/PS_LOCK.md` goes here with a date and owner. Assumptions
that affect behaviour must live in configuration, not hard-coded logic.

| ID | Date | Assumption | Where configured | Status |
|---|---|---|---|---|
| A1 | 2026-10-30 | SLA targets in seed data are fictional | `sla_policies` | Open |
| A2 | 2026-10-30 | Costly-repair threshold is ₹25,000 | `approval_rules` | Open |
| A3 | 2026-10-30 | Booking and assignment slots are 15 minutes | `collision_rules` | Open |
| A4 | 2026-10-30 | A technician's soft limit is 3 concurrent tasks | `collision_rules` | Open |
| A5 | 2026-10-30 | Duplicate gating window is 48 hours | ML settings | Open |
| A6 | 2026-10-30 | Student/Faculty are two separate roles, giving seven roles in total | `roles_permissions` | Open |
| A7 | 2026-10-30 | Hard collisions can never be overridden | `collision_rules` | Open |

## Platform checks (Phase 1)

| Check | Result |
|---|---|
| Multi-document transactions work on our Atlas tier | Not yet tested |
| Median plan can export an installable Android APK | Not yet confirmed |
| Login survives app restart in Median | Not yet tested |
| Backend and ML fit in deployed memory | Not yet measured |
| Calling external AI APIs is allowed at the event | Ask organisers |

## Phases 4 to 6 (added 2026-10-30)

| ID | Date | Assumption | Where it lives | Status |
|---|---|---|---|---|
| A8 | 2026-10-30 | Priority comes from a fixed table of urgency to P1-P4. Five or more reports raise it one step, and it is never lowered. | `app/incidents/policy.py` | Open |
| A9 | 2026-10-30 | A new report joins an open incident of the same category in the same building within 48 hours when it names the same room, reads at least 0.6 alike, or (network and electrical only) reads at least 0.2 alike, or 0.12 once the incident already has company. With similarity scoring off, the same room, or any area-wide fault in the building, joins. | `app/incidents/service.py` | Open |
| A10 | 2026-10-30 | Bookings run in 15 minute steps, last 15 minutes to 12 hours, and open 120 days ahead. They confirm immediately when the collision check passes, with no approval step. | `app/bookings/service.py` | Open |
| A11 | 2026-10-30 | Booking outside a building's opening hours is a warning that needs a reason, not a block. | `collision_rules` ROOM-006 | Open |
| A12 | 2026-10-30 | Departments are matched on the department of the person who booked, so a department manager sees the bookings of their own staff. | `bookings.departmentId` | Open |
| A13 | 2026-10-30 | Collision review is campus-wide for the two roles that hold it, because it records decisions rather than personal data. | `GET /collisions` | Open |
| A14 | 2026-10-30 | A classroom booking is overridden only by a reason (soft findings) or by an approved override bound to the exact action (approval findings). Hard findings are never overridable. | `app/collision/engine.py` | Open |
| A15 | 2026-10-30 | Each incident category maps to one required skill and minimum level, an estimated duration, and a safety note (for example ELECTRICAL needs level 2, 90 minutes). The ranking weights are skill 30, workload 25, start time 20, shift 15, proximity 10. | `app/workorders/policy.py` | Open |
| A16 | 2026-10-30 | The plan's `CREATED` state is folded into `PENDING_ASSIGNMENT`, and `RESUMED` is the `RESUME` event back to `IN_PROGRESS`, so there is one less state to explain and test. | `app/workorders/state.py` | Open |
| A17 | 2026-10-30 | Preemption and event-driven reassignment only flag work and propose a replacement. Nothing moves until a Facilities or Department manager confirms. | `WorkOrderService.flag` | Open |
| A18 | 2026-10-30 | Work not accepted within 10/30/120/240 minutes (P1 to P4), or running 15 minutes past its slot, is flagged as late. | `app/workorders/policy.py` | Open |
| A19 | 2026-10-30 | The person who did a repair cannot verify it. Verification is by a different user holding `workorder.verify`. | `WorkOrderService.verify` | Open |
| A20 | 2026-10-30 | An outage is assumed to disturb the timetable for the next 24 hours, and an impact snapshot older than 15 minutes is recomputed on read. | `app/cascade/service.py` | Open |
| A21 | 2026-10-30 | A report names rooms, not assets. Triage names the faulty asset (for example a transformer) through `POST /cascading/impact/{id}/recompute`, which is what extends the chain beyond the reported rooms. | `incident.assetIds` | Open |
| A22 | 2026-10-30 | People told about an impact are only the lecturers and student-group members of the affected classes. | `CascadeService._recipients` | Open |
