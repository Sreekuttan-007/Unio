# UNIO — API Contract

Base path `/api/v1`. The generated OpenAPI document at `/openapi.json` is the exact
contract, and `npm run gen:api` produces the frontend types from it. This file records
conventions and endpoint groups.

## Conventions

| Topic | Rule |
|---|---|
| Format | JSON, UTC ISO-8601 timestamps |
| Auth | `Authorization: Bearer <jwt>` |
| Lists | `?page=0&size=20&sort=createdAt,desc`, response `{items, page, size, total}` |
| Retryable writes | `Idempotency-Key: <uuid>` |
| Tracing | `X-Correlation-Id`, generated if missing and returned on the response |
| Entity responses | Include `availableActions` and `unavailableActions` |
| Out-of-scope rows | `404` |

## Errors

```json
{
  "code": "ROOM_OVERLAP",
  "message": "ARB-204 is already booked from 09:00 to 11:00.",
  "details": {},
  "correlationId": "c0a1f3"
}
```

| Status | Meaning |
|---|---|
| 400 | Validation failed |
| 401 | Not authenticated |
| 403 | Permission missing |
| 404 | Not found or out of scope |
| 409 | Version conflict, or an idempotency key reused with a different body |
| 422 | Business rule failed, including hard collisions and self-approval |
| 429 | Rate limited |
| 503 | Dependency unavailable |

## Collision result

Returned from checks, and in a `422` when a commit is blocked:

```json
{
  "decision": "BLOCK",
  "checkId": "CC-5100",
  "findings": [{
    "code": "TECHNICIAN_OVERLAP",
    "severity": "HARD",
    "message": "Ravi already has WO-099 from 09:00 to 10:30.",
    "affected": [{ "type": "TECHNICIAN", "id": "T-08" }],
    "ruleId": "TECH-002"
  }],
  "alternatives": [{ "label": "Assign Meena (T-11)", "action": {} }]
}
```

`decision` is one of `ALLOW`, `WARN`, `REQUIRE_APPROVAL`, `BLOCK`.

## Endpoints

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout` |
| Me | `GET /me/bootstrap`, `GET /me/badges`, `PATCH /me/profile` |
| Campus | `GET /campus/buildings`, `/rooms`, `/assets`, `/map`, `/map/overlays` |
| Timetable | `GET /timetable/sessions`, `GET /timetable/affected?incidentId=` |
| Issues | `POST /issues`, `GET /issues`, `GET /issues/{id}`, `POST /issues/{id}/clarify`, `POST /issues/{id}/feedback` |
| Chat | `POST /chat/sessions`, `POST /chat/sessions/{id}/messages`, `POST /chat/sessions/{id}/submit` |
| Inbox | `GET /inbox`, `POST /inbox/simulate`, `POST /inbox/{id}/process` |
| Incidents | `GET /incidents`, `GET /incidents/{id}`, `POST /incidents/{id}/transition`, `POST /incidents/{id}/link`, `POST /incidents/{id}/split`, `POST /incidents/{id}/summary/regenerate` |
| Bookings | `GET /bookings`, `POST /bookings`, `GET /bookings/availability`, `GET /bookings/alternatives`, `POST /bookings/{id}/cancel`, `POST /bookings/{id}/reschedule` |
| Work orders | `GET /work-orders`, `POST /work-orders`, `GET /work-orders/{id}`, `GET /work-orders/{id}/candidates`, `POST /work-orders/{id}/assign`, `/accept`, `/decline`, `/start`, `/block`, `/resume`, `/complete`, `/verify`, `/reassign` |
| Technicians | `GET /technicians`, `GET /technicians/{id}`, `PATCH /technicians/{id}/availability`, `GET /technicians/workload` |
| Collisions | `POST /collisions/check`, `GET /collisions`, `GET /collisions/{id}` |
| Cascade | `GET /cascading/impact/{incidentId}`, `POST /cascading/impact/{incidentId}/recompute` |
| Simulator | `POST /simulations`, `GET /simulations/{id}`, `POST /simulations/{id}/plans/{planId}/execute` |
| Inventory | `GET /inventory/items`, `GET /inventory/balances`, `POST /inventory/reservations`, `POST /inventory/reservations/{id}/release`, `GET /inventory/transactions` |
| Approvals | `POST /approvals`, `GET /approvals`, `GET /approvals/{id}`, `POST /approvals/{id}/submit`, `POST /approvals/{id}/decide`, `POST /approvals/{id}/execute` |
| Procurement | `GET /procurement/orders`, `POST /procurement/orders` |
| Invoices | `POST /invoices`, `GET /invoices`, `GET /invoices/{id}`, `PATCH /invoices/{id}/fields`, `POST /invoices/{id}/match`, `POST /invoices/{id}/validate` |
| Goods receipts | `POST /goods-receipts`, `GET /goods-receipts`, `POST /goods-receipts/{id}/validate` |
| SLA | `GET /sla/instances`, `GET /sla/summary`, `POST /sla/instances/{id}/pause`, `POST /sla/instances/{id}/resume` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Analytics | `GET /analytics/open-requests`, `/sla-compliance`, `/utilisation`, `/shortages`, `/recurring-incidents` |
| Audit | `GET /audit` |
| Webhooks | `POST /webhooks/inbound/{source}` (signed), `GET /admin/webhooks`, `POST /admin/webhooks`, `POST /admin/webhooks/{id}/test` |
| Admin | `/admin/users`, `/admin/roles`, `/admin/campus`, `/admin/staff`, `/admin/inventory-items`, `/admin/rules`, `/admin/sla-policies`, `/admin/integrations`, `/admin/scenarios/{id}/reset` |

Every endpoint gets a row in `permission-matrix.csv` in the same PR that adds it.
