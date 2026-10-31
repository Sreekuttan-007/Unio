# Contributing to UNIO

Thanks for working on this. This file is the human-readable version of the working rules; a
coding agent follows the longer [AGENTS.md](AGENTS.md), which outranks this file if the two ever
disagree.

## Setup

Follow [README.md](README.md) to get the backend and frontend running locally. You'll need
Python 3.12+, Node.js 22+, and npm.

## Before you touch code

1. Read [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the build order and the phase a
   change belongs to.
2. Check [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md), [docs/DATA_MODEL.md](docs/DATA_MODEL.md),
   and [docs/RBAC_AND_NAVIGATION.md](docs/RBAC_AND_NAVIGATION.md) — if what you need isn't
   written down there or in the plan, it's an assumption. Write it into `ASSUMPTIONS.md` with
   today's date rather than burying an invented business rule in a service class.

## Non-negotiable rules

These are enforced by tests, not just convention:

- **The backend decides everything.** RBAC, data scope, collisions, state transitions,
  approvals, inventory math, SLA. The frontend renders decisions; it never computes which
  buttons a user may press or where their navigation goes — both come from the API.
- **Simulation never writes to live data.** An import-boundary test enforces this on
  `app/simulation/`.
- **No self-approval**, enforced server-side and tested.
- **Every write that matters is audited**, and every retryable write accepts
  `Idempotency-Key`.
- **Every API route declares its access** via `require(...)`, `authenticated`, or
  `dependencies=[public]`. A new route needs a row in `backend/tests/permission_matrix.csv` or
  the coverage test fails the build.
- **Frontend layers stay separate**: `ui/` is presentation-only (props in, no data fetching),
  `features/` fetches and wires, `platform/` is frozen (auth, API client, router, workspace
  registry — ask before editing). `npm run lint` enforces this.

## Changing the API contract

If you add or change a route, schema, permission, or navigation item:

```bash
cd backend && python -m tools.contract
cd frontend && npm run gen:api
```

Commit the regenerated files (`frontend/src/types/openapi.json`,
`frontend/src/types/api.generated.ts`, `frontend/src/mocks/fixtures/generated.json`). CI fails
if they're stale. If the frontend needs the new endpoint before the real integration is wired
up, add a handler to `frontend/src/mocks/domainHandlers.ts` in the same change so
`npm run dev:mock` keeps working.

## Before opening a PR

Run every gate and don't open a PR with a red one:

```bash
# Backend
cd backend
.venv/Scripts/python -m ruff check app tests tools   # must be clean
.venv/Scripts/python -m mypy app                      # advisory - see the note in pyproject.toml
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m tools.contract --check

# Frontend
cd frontend
npm run typecheck && npm run lint && npm test && npm run build
```

For a UI change, also run the phone-width check (needs Playwright installed globally:
`npm install -g playwright && npx playwright install chromium`):

```bash
NODE_PATH=$(npm root -g) node scripts/phone-check.mjs http://localhost:5173
```

## Commits and branches

- One topic per branch, named for what it does (`feat/webhook-management`,
  `fix/invoice-overflow`).
- [Conventional commits](https://www.conventionalcommits.org/): `feat(collision): add
  technician shift rule`, `fix(inventory): correct reorder threshold comparison`.
- Run `git status` before every commit and check what's staged — never commit a `.env` file, a
  credential, or output from a debugging session.
- A commit message says what changed and why, and names the tests that cover it. "This should
  work" is not a substitute for running the tests and pasting the result.

## What "done" means

A feature is done when it works end to end through the real API and the real UI, not when a
mock passes. If you're short on time, finish a smaller slice completely rather than leaving a
larger one half-wired — and say explicitly what's left out and why, in the PR description and in
[docs/HANDOFF.md](docs/HANDOFF.md) if it affects the overall project status.
