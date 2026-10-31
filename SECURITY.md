# Security Policy

UNIO is a prototype built for a campus-operations challenge. It is not yet hardened for
production use with real personal data — see the caveats below — but we still want to know
about real problems.

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security problem. Instead, use
[GitHub's private vulnerability reporting](https://github.com/Sreekuttan-007/Unio/security/advisories/new)
on this repository (Security tab → "Report a vulnerability"). That opens a private conversation
with the maintainers only.

Include, if you can:

- What you found and where (file, route, or screen).
- Steps to reproduce.
- What you'd expect to happen instead.

There's no formal SLA on this project yet — it's maintained by a small team — but we'll
acknowledge a report as soon as we see it and fix anything real.

## Current known limitations

Being upfront about where the security posture is intentionally incomplete, so a report doesn't
need to rediscover these:

- **Demo mode** (`DEMO_MODE_ENABLED=true`) allows tap-to-sign-in with no password. It must be
  `false` for any deployment holding real data. The seed demo password
  (`DEV_DEMO_PASSWORD` in `backend/app/config.py`) is intentionally public — it is never meant
  to guard anything real.
- **Login rate limiting** (`app/core/security.py`) is in-memory and per-process. It resets on
  restart and doesn't share state across multiple backend instances.
- **No refresh tokens.** A session is one JWT with a fixed TTL; there is no revoke-and-reissue
  flow beyond the explicit logout/`revoked_tokens` path.
- **File uploads** are stored as blobs directly in MongoDB (`app/files/service.py`), not in
  dedicated object storage, despite that being the documented intent in
  `docs/DEPLOYMENT.md`. Fine for a prototype's data volumes; not fine at scale.
- **Inbound webhooks** are refused by design (`app/notify/service.py`, assumption A33 in
  `docs/ASSUMPTIONS.md`) — only outbound, signed webhooks exist. Opening a public inbound route
  is a deliberate decision for whoever runs this, not something to add casually.

## What's already handled

- Passwords are hashed with Argon2 (`argon2-cffi`), never stored or logged in plaintext.
- Every API route explicitly declares its access level; a route with no declared guard fails
  application startup (`assert_all_routes_guarded`), and `backend/tests/permission_matrix.csv`
  is tested against every real role for every route.
- Every meaningful write is audited (actor, role, action, entity, before/after, reason,
  correlation id) in an append-only `audit_logs` collection with no update or delete path.
- Retryable writes accept an `Idempotency-Key`; state transitions use compare-and-set, so a
  repeated or concurrent request can't double-apply.
- Security headers are set on every response (`app/core/headers.py`).
