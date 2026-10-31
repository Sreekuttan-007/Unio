# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); dates are when the work landed, not
necessarily when it was planned.

## Unreleased

### Added

- Affected people are actually notified when a cascade refresh adds them to an incident's
  impact, once per person per change (`impact.changed`).
- Low-stock reorder alerts: crossing an item's reorder threshold notifies Procurement once,
  and again the next time it drops low after recovering.
- Requesters can answer an approval's clarification question from the UI
  (`POST /approvals/{id}/answer` already existed server-side; it had no screen).
- Webhook management: add, edit, enable/disable a webhook, view its delivery log, and replay
  a past delivery (proves the redelivery-safety guarantee live).
- Two more What-If Simulator plans — "repair in the next free window" (waits for a technician's
  real in-shift slot instead of forcing an immediate assignment) and "use stock, or raise a
  purchase" (checks short parts against live stock through the same rule a real request uses) —
  plus an SLA-margin metric on every plan.
- `scripts/phone-check.mjs` now takes a width and a `--dark` flag, so 1440px and dark mode are
  checked alongside the original 360px/light pass.
- `scripts/scenario-check.mjs`: Playwright click-through for demo Scenarios A–D, resetting each
  one through the real Admin screen and confirming its story is visible in the real UI.
- `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md`, this changelog.

### Fixed

- The Invoices and Discrepancies screens scrolled the whole page sideways by 82px at desktop
  widths — a CSS grid column missing `min-w-0` let the invoice-lines table's intrinsic width
  push past the viewport instead of scrolling inside its own card. Found by the new 1440px
  phone-check pass.

### Changed

- `app/sla/service.py`'s pure SLA-clock arithmetic moved to a new `app/sla/timer.py`, so the
  simulator's planner can read it without importing a `.service` module (which the
  import-boundary test treats as a write path). No behavior change; `sla/service.py` re-exports
  the same functions for existing callers.

## Phases 7–13 — 2026-10-30

The core feature build, each phase on its own commit/branch with a `phase-NN-green` tag:

- **Phase 7 — Work orders.** Assignment and technician workflows; fixed a race where the loser
  of a concurrent assignment deleted the winner's technician slots.
- **Phase 8 — Cascading impact.** Pure BFS over `dependency_edges`, impact snapshots, map
  overlays, faculty-scoped academic view.
- **Phase 9 — What-if simulator.** An in-memory snapshot reader, three rule-based recovery
  plans judged by the live collision engine, fingerprint-checked execution.
- **Phase 10 — Inventory and procurement.** CAS stock reservations, the stock ledger with a
  startup reconciler, approval routing, invoice-to-inventory with goods receipts.
- **Phase 11 — SLA, notifications, webhooks, analytics.** Escalation sweep, in-app
  notifications, signed outbound webhooks, analytics against a known-answer fixture.
- **Phase 12 — Workspace polish.** Session rescheduling and class moves from triage, mock mode
  working on a fresh clone, 360px phone-width verification.
- **Phase 13 — Harden.** One-click scenario reset for demos A–D, security pass.

## Initial commit — 2026-10-30

Phases 0–6: the walking skeleton, identity and RBAC, campus master data, incident intake with
ML triage, the collision engine, and room bookings. See
[docs/HANDOFF.md](docs/HANDOFF.md) for what's built versus what's left.
