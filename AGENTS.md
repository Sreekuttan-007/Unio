# UNIO — Agent Working Rules

Read by Antigravity, Claude Code, and any other coding agent before touching this repo.
This file outranks a model's own instincts. If a rule here conflicts with what seems
convenient, the rule wins.

**Stack:** React + TypeScript (Vite, Tailwind v4) · Python FastAPI backend · MongoDB Atlas ·
Gemini for the LLM parts · Median.co wraps the deployed site as an Android app.

---

## 1. Source of truth order

1. The official challenge brief supplied by the user or team. It is not reproduced in this repository.
2. `IMPLEMENTATION_PLAN.md` — build order, phase gates, and agreed scope.
3. `docs/DATA_MODEL.md`, `docs/RBAC_AND_NAVIGATION.md`, `docs/ML_SERVICE.md`, `docs/DEPLOYMENT.md`, and `docs/ASSUMPTIONS.md`.
4. Existing code.

If a requirement is not in 1–3, it is an **assumption**. Write it into
`docs/ASSUMPTIONS.md` with a date and isolate it in configuration. Do not bury an
invented business rule inside a service class.

---

## 2. Commands

```bash
# backend (from backend/)
.venv/Scripts/python -m pytest -q                 # all tests
.venv/Scripts/python dev_server.py                # API on :8000, in-memory data, demo accounts
.venv/Scripts/python -m tools.contract            # refresh the frontend contract (see section 7)

# frontend (from frontend/)
npm run dev                                       # talks to the backend on :8000
npm run dev:mock                                  # no backend: served by src/mocks
npm run typecheck && npm run lint && npm test     # the three gates
npm run build
```

Open `/dev/ui` in development for the component gallery. A change is not done until the
three frontend gates and the backend tests all pass.

---

## 3. The three-layer rule (this is what keeps UI tuning safe)

```
frontend/src/ui/        PRESENTATION ONLY.  Antigravity's playground.
frontend/src/features/  CONTAINERS. Data fetching and wiring. Edit with care.
frontend/src/platform/  FROZEN. Auth, api client, router, workspace registry.
```

- `ui/` components receive **props only**. No `useQuery`, no `fetch`, no `useAuth`,
  no permission checks, no routing. A `ui/` component must render correctly from a plain
  object. That is why Antigravity can restyle the whole app without being able to break
  authorization.
- `features/` may fetch and call hooks, but holds no raw colours or pixel sizes. Only
  design tokens and `ui/` components.
- `platform/` is in the freeze list below.
- **`npm run lint` enforces this.** It fails on a `ui/` file that imports platform, features,
  the router or a data library, and on any raw hex colour, colour function or arbitrary
  pixel size outside `styles/tokens.css`.

**Test for the boundary:** if a `ui/` component cannot be shown in `/dev/ui` with hand-written
props, it is in the wrong layer.

---

## 4. Freeze list — do not edit without an explicit human instruction

```
frontend/src/platform/**                       auth, http client, router, workspace registry
frontend/src/types/api.generated.ts            generated: run `npm run gen:api`, never hand-edit
frontend/src/types/openapi.json                generated: run `python -m tools.contract`
frontend/src/mocks/fixtures/generated.json     generated: run `python -m tools.contract`
backend/app/core/permission.py                 the permission list (append only)
backend/app/core/access.py                     endpoint guards and the public allowlist
backend/app/core/scope.py                      data-scope filters
backend/app/core/identity.py, security.py      sign-in and tokens
backend/app/ml/schemas.py                      AI request and response contracts
.github/workflows/**
.env, .env.local, backend/.env
```

To change a frozen file: state why, what breaks, and get a human yes first. Adding a new
permission or a new public route is exactly that kind of change.

---

## 5. Non-negotiable architecture rules

1. **The backend decides. Always.** RBAC, data scope, collisions, state transitions,
   approvals, inventory maths, SLA. The frontend renders decisions and never makes them.
2. **The frontend never computes which buttons a user may press.** Entity responses carry
   `availableActions` and `unavailableActions` (with a reason) from the backend. A disabled
   button in React is a cosmetic hint, not a control.
3. **The frontend never computes its own navigation.** `GET /api/v1/me/bootstrap` returns the
   role's navigation. Routes not in it are not mounted, and each workspace is its own code chunk.
4. **AI suggests; deterministic code decides.** AI output is stored as an `ai_suggestion` with a
   model version and confidence. It never writes an authoritative field. Every workflow must
   still work with AI off (PS constraint C6).
5. **Simulation is read-only.** A simulation run may not write to a live collection. Ever.
6. **Invoice upload never moves stock.** Stock moves only through a ledger entry created by an
   authorised goods receipt.
7. **No self-approval.** Enforced in the backend, tested.
8. **Every write that matters is audited:** actor, role, action, entity, before and after,
   reason, correlation id.
9. **Writes that can be retried accept `Idempotency-Key`** (PS constraint C4), and state changes
   use compare-and-set (`app/core/state.py`), so a repeated event applies once.
10. **Every route declares its access** with `require(...)`, `authenticated` or
    `dependencies=[public]` on a `GuardedRouter`. Adding a route also means adding a row to
    `backend/tests/permission_matrix.csv`, or the coverage test fails.
11. **The campus is fictional (PS constraint C2).** The map is our own SVG with stable region ids
    bound to `buildings` and `rooms`. Do not present it as a GPS map.

---

## 6. Styling rules

- Every colour, radius, shadow, size and font is defined in `frontend/src/styles/tokens.css`
  and exposed to Tailwind in `styles/index.css` (`bg-surface`, `text-muted`, `bg-accent`...).
- Dark mode is `[data-theme="dark"]` plus a `prefers-color-scheme` fallback. Define both for
  every token.
- The role accent comes from the server (`data-accent` on the page). Use `accent` tokens, never
  a hard-coded hue, so every role keeps its own identity.
- Mobile first. Check 360px before 1440px. No sideways page scroll.
- `100dvh`, never `100vh` (Median WebView address bar).
- Minimum touch target 44px. No hover-only controls. Status is never colour alone: add text or
  an icon.

---

## 7. Parallel work: tuning the UI while the backend changes

```bash
cd frontend && npm run dev:mock
```

MSW serves every endpoint from `frontend/src/mocks/handlers.ts`. The bootstrap, role and user
fixtures are **generated from the real backend**, so they cannot drift:

- After changing a route, schema, permission, navigation item or role, run
  `python -m tools.contract` in `backend/`, then `npm run gen:api` in `frontend/`, and commit
  the result. Backend tests and CI fail if the committed files are stale.
- If you add an endpoint the UI needs, add a handler to `mocks/handlers.ts` in the same change.
- A new navigation key needs a screen in the right `features/workspaces/<role>/index.tsx` and
  an entry in `platform/workspaces/registry.ts`. Tests fail on a missing or orphan screen.
- Frontend work stays in `frontend/**`. Backend work stays in `backend/**`. The shared surface is
  the generated contract and `docs/API_CONTRACT.md`. Announce changes to it in the PR title.

---

## 8. How to run a task

Before editing: report the repo state in a paragraph, name the phase from `IMPLEMENTATION_PLAN.md`,
and for anything touching more than three files post a short plan.

While editing: implement only the requested phase, add tests for every business rule, keep
passing tests passing.

After editing: run the real tests and the real build and paste the output. List files changed,
commands run, results, known gaps and the next step. **Never report a feature complete unless it
works end to end.** A passing mock is not a working feature.

Forbidden: fabricated test output, "this should work", deleting a failing test to go green,
committing secrets, `--force` pushes, and weakening a permission or scope rule to make a test pass.

---

## 9. Commit discipline

- One phase per branch: `phase/07-work-orders`.
- Conventional commits: `feat(collision): add technician shift rule`.
- Commit at every green phase gate and tag it: `git tag phase-07-green`. The demo must always
  be able to fall back to the last green tag.
- `git status` before every commit. The repository root is `overclock-hack`, never the home folder.
