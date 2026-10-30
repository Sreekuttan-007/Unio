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
| A23 | 2026-10-30 | The simulator plans for classes in the next 24 hours, at most 12 per run, and leaves classes starting within 15 minutes where they are. It compares five rule-based plans: move within the building, move anywhere, repair now, repair in the technician's next free in-shift window, and use stock vs raise a purchase. Every plan also reports the incident's own SLA margin (not simulated per plan, just read live). | `app/simulation/planner.py` | Open |
| A24 | 2026-10-30 | The recommended plan is the feasible one that moves the fewest people, then needs the fewest acknowledged warnings. Executing a plan acknowledges its soft findings with the reason "Recovery plan X from simulation Y". | `app/simulation/planner.py`, `service.py` | Open |
| A25 | 2026-10-30 | LLM narration of plans is not built: plan summaries are written by deterministic code from the stored numbers. | `app/simulation/planner.py` | Open |
| A26 | 2026-10-30 | Purchases go to a Procurement Approver; costly repairs up to ₹25,000 to a Department Manager and above that to Procurement; overrides to the Facilities Administrator. Each approver can approve only up to their own limit. | `approval_rules`, `app/approvals/policy.py` | Open |
| A27 | 2026-10-30 | Three fictional suppliers, chosen by the item's category. One purchase order per approved request, from the supplier of its first line. | `suppliers` | Open |
| A28 | 2026-10-30 | A shortage raises the purchase request in the technician's name, so the technician can never be its approver. A reservation takes the whole quantity from one store or nothing. | `app/inventory/service.py` | Open |
| A29 | 2026-10-30 | Validating an invoice records the delivery (the validator is the receiver) and creates a pending goods receipt; a different person, who also did not raise the request, validates the receipt, which posts stock to the Central Store once. | `app/procurement/service.py` | Open |
| A30 | 2026-10-30 | Invoices are read by a deterministic text reader (plain text and text PDFs). Photos and scanned PDFs need the optional AI reader, which is not wired yet, so they arrive with a "nothing read" discrepancy for a person to handle. | `app/procurement/service.py` | Open |
| A31 | 2026-10-30 | Stock levels are not sensitive, so department managers see campus-wide stock; technicians see only the part catalogue with free quantities and their own reserved parts. | `GET /inventory/items`, `/inventory/catalog` | Open |
| A32 | 2026-10-30 | The SLA escalation sweep runs on the outbox timer and on demand. Level 1 (75%) tells the managers of the work's department, falling back to Facilities when there are none; level 2 (100%) tells Facilities. A paused clock never escalates. | `app/sla/board.py`, `sla_policies` | Open |
| A33 | 2026-10-30 | Webhooks are outbound only, signed with HMAC-SHA256 in `X-Unio-Signature`. A built-in receiver (`internal://receiver`) demonstrates signature checks and replay protection. Inbound webhooks from outside need a new public route, a frozen-file change that has not been approved. | `app/notify/service.py` | Open |
| A34 | 2026-10-30 | Room utilisation is booked minutes over bookable rooms times 14 opening hours; technician utilisation is scheduled work minutes over shift minutes, both for the current campus day. Recurring means the same category in the same room at least twice in 90 days. | `app/analytics/service.py` | Open |
| A35 | 2026-10-30 | The ML "SLA risk" signal is not built; SLA rows return `risk: null`. | `app/sla/board.py` | Open |
| A36 | 2026-10-30 | A scenario reset wipes operational data and reseeds the campus, keeping users, roles, rules, policies and the audit trail. It only runs when demo mode is on, and gives every technician a shift around the current time so demos work at any hour. | `app/scenarios/service.py` | Open |
| A37 | 2026-10-30 | A cascade refresh tells only the people the chain just added to `recipientUserIds`, once per person per refresh that adds them. A refresh that leaves the recipient set unchanged (nobody new) notifies nobody again. | `app/cascade/service.py` `refresh()` | Open |
| A38 | 2026-10-30 | An item's free stock (on hand minus reserved, summed across stores) is checked after every reservation, release and goods receipt. Crossing to or below `reorderThreshold` tells Procurement once; it recovers (and can fire again) only once free stock rises back above the threshold. | `app/inventory/service.py` `_check_reorder()` | Open |
| A39 | 2026-10-30 | A webhook delivery keeps its event's payload alongside its status, so a replay never needs the original outbox event to still exist. Replaying an already-successful delivery reuses the existing `(webhook, event)` key and sends nothing twice. | `app/notify/service.py` `WebhookService.replay()` | Open |
| A40 | 2026-10-30 | "Repair in the next free window" only counts a technician's genuine in-shift slot (never an urgent, out-of-shift start) and picks the earliest one, through the same ASSIGN_TECHNICIAN check live assignment uses. | `app/simulation/planner.py` `_repair_next_window_plan()` | Open |
| A41 | 2026-10-30 | "Use stock vs buy" checks each short part through the same RESERVE_PARTS rule a live request uses. A needed purchase is a finding, not a blocker: the plan stays feasible, it just says what must be bought and an estimate of the cost. | `app/simulation/planner.py` `_stock_vs_buy_plan()` | Open |
