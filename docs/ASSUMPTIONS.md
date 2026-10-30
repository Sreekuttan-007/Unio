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
