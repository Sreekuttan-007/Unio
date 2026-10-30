# UNIO — Deployment and Median APK

## 1. Topology

```
Android APK (Median)  ──┐
                        ├── HTTPS ──> Frontend (Vercel, static React build)
Desktop browser ────────┘                     │  REST + Bearer token
                                              ▼
                                 Backend (FastAPI, Docker, one service)
                                   │                     │
                                   ▼                     ▼
                           MongoDB Atlas          Gemini API
                                                  (summaries, invoice reading)

Evidence and invoice files ──> S3-compatible object storage (Phase 4 onward)
```

Median loads the deployed site, so **the web URL is the app**. Median says site changes show up in
the app immediately. A UI change that reaches Vercel reaches the phone with no APK rebuild, which is
why UI tuning and deployment do not conflict.

The AI and ML code runs inside the backend, so there are only two things to host: the frontend and
the backend. See `docs/ML_SERVICE.md`.

## 2. Hosting

| Service | Host | Why |
|---|---|---|
| Frontend | Vercel | A preview URL for every branch, which suits UI tuning |
| Backend | Render web service (Docker) | Simple Docker deploys and health checks |
| Database | MongoDB Atlas | The project requires a persistent database |
| Files | S3-compatible storage behind a `FileStorage` interface | Render's filesystem does not persist |

Files already in the repo for this: `backend/Dockerfile`, `docker-compose.yml`, `render.yaml`,
`frontend/vercel.json`, and `.github/workflows/ci.yml`. Docker could not be run on the machine
where these were written (the Docker engine was not running), so **the first image build and the
`render.yaml` blueprint are untested**. Do a build and a deploy in Phase 1, not on demo day.

### The free tier is not suitable for demo day

Third-party sources report these Render free-tier limits. Confirm them on Render's own pricing page
before relying on them.

| Limit | Effect on UNIO |
|---|---|
| 512 MB RAM, 0.1 CPU | Tight once trained models are loaded, so measure it |
| Sleeps after 15 idle minutes | About a minute to wake, which ruins a live demo |
| Sleeping stops background jobs | The SLA sweep and the email poller pause |
| Ephemeral filesystem | Local uploads vanish |

**Recommendation:** develop on free, then move the backend to an always-on instance at least 24
hours before judging. Starter is reported at $7 a month. Paying is your decision, but a sleeping
backend during judging is the biggest avoidable demo risk here.

The code already tolerates sleeping: the login screen pings the server and shows "waking the
server" after three seconds instead of looking broken, SLA state is computed on read as well as by
the background sweep, and the API client allows a long first request.

## 3. Running it

### Local, no database needed

```
backend:   .venv\Scripts\python dev_server.py        in-memory data, demo accounts, port 8000
frontend:  npm run dev                               port 5173, talks to the backend
frontend:  npm run dev:mock                          no backend at all, served by mocks
```

`dev_server.py` uses an in-memory mock of MongoDB. Everything resets on restart, and it cannot
prove the unique-index and concurrency guarantees, which need a real database.

### Local, real database

```
docker compose up --build        MongoDB 8 plus the API on port 8000 (needs Docker Desktop running)
```

Or point `MONGODB_URI` at an Atlas cluster.

### Running the backend tests against a real MongoDB

By default the backend tests use an in-memory mock. To run the same tests against a real
database, set `MONGODB_TEST_URI` (an Atlas cluster or a local `mongod`). Each test run creates
and drops its own uniquely named database. **Do this before relying on the idempotency and
double-booking guarantees**, and again in Phase 6 when the slot-claim tests arrive.

## 4. Environment variables

Backend names match `backend/app/config.py`. Copy `backend/.env.example` to `backend/.env` locally.

| Variable | Secret | Notes |
|---|---|---|
| `APP_ENV` | No | `dev` allows a built-in development secret. Anything else requires `JWT_SECRET` |
| `MONGODB_URI` | Yes | A least-privilege database user |
| `MONGODB_DATABASE` | No | Defaults to `unio` |
| `JWT_SECRET` | Yes | At least 32 bytes. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_TTL_MINUTES` | No | Defaults to 480 |
| `CORS_ALLOWED_ORIGINS` | No | Comma separated: the Vercel production URL and preview pattern |
| `DEMO_MODE_ENABLED` | No | Seeds demo accounts and enables one-tap sign-in. **Off for anything real** |
| `DEMO_USER_PASSWORD` | Yes | Password for password sign-in on demo accounts. Unset means one-tap only |
| `GEMINI_API_KEY` | Yes | Backend only. Never in the frontend |
| `GEMINI_MODEL` | No | Defaults to `gemini-3.8-flash` (from Phase 4) |
| `LLM_PROVIDER` | No | `gemini` or `disabled` (from Phase 4) |
| `API_DOCS_ENABLED` | No | Serves `/docs` and `/openapi.json`. Turn off in production |
| `VITE_API_BASE_URL` | No | Frontend: the backend origin only, with no path. Public by nature |
| `VITE_USE_MOCKS` | No | Frontend: `true` only for `npm run dev:mock` |

Anything prefixed `VITE_` is shipped to the browser. Never commit a real `.env`.

**Demo mode on a deployed host.** `render.yaml` turns demo mode on so the judging build has tap-to-
sign-in chips. That is appropriate for a hackathon demo and wrong for anything real, because anyone
can then sign in as any seeded role. Turn it off afterwards.

## 5. Authentication and the WebView

A JWT bearer token kept in `localStorage` and sent in the `Authorization` header. It avoids
cross-site cookie problems between Vercel and Render and needs no CSRF handling. The cost is that
script injection could read the token, so tokens are short-lived, signing out revokes them
server-side, API responses carry a strict content security policy, and the frontend never renders
raw HTML.

Median's docs that we found do not cover `localStorage` persistence, so Phase 1 tests it on a real
device: sign in, kill the app, reopen. If the session does not survive, research Median's
secure-storage options at that point.

## 6. Atlas setup

1. Create a free cluster near the Render region, in a dedicated project.
2. Create a database user limited to read and write on `unio`.
3. Render's outbound IPs may vary, so a hackathon deployment may need `0.0.0.0/0` network access.
   If so, rely on a strong generated password and remove the rule afterwards.
4. The design needs no multi-document transactions, because every guarantee rests on single-document
   atomic writes and unique indexes. You can note whether your tier supports transactions, but
   nothing depends on it.
5. Keep file bytes out of the database. Free clusters have small storage and a transfer limit over
   a rolling seven-day period, according to Atlas docs.

## 7. Frontend deployment

`frontend/vercel.json` rewrites every path to `index.html` so deep links work.

- Root directory `frontend`, build command `npm run build`, output `dist`.
- Set `VITE_API_BASE_URL` to the Render backend origin.
- Branch pushes create preview URLs. Add the preview origin to `CORS_ALLOWED_ORIGINS`.

## 8. Median APK

### First: check the plan

Sources agree that Median's free tier shows a "Powered by Median.co" watermark, but none confirmed
that it can export a sideloadable APK. Paid pricing also differs between sources. Check Median's
pricing page and App Studio in Phase 1, **before the demo depends on it**. If the free plan cannot
export, decide then between paying and a fallback.

### Steps

1. Deploy the frontend and confirm the production URL works in a phone browser.
2. Create a Median app pointing at the production URL.
3. Set the app name, icon and splash from `frontend/public/brand/`.
4. Keep navigation inside the UNIO domain and open other links externally.
5. Build for Android and install on a physical phone.
6. Run the device checks below.

Verify each setting's current name in App Studio, because labels change.

### What the web app already does for a good WebView

| Requirement | Where |
|---|---|
| Viewport with `viewport-fit=cover` | `frontend/index.html` |
| `100dvh`, never `100vh` | `styles/index.css` |
| Safe-area padding on the top bar and bottom nav | `ui/shell/*` |
| Standard file input for camera and gallery (Median's documented path) | Phase 4 |
| 44px touch targets, no hover-only actions | `ui/` components |
| No page bounce | `overscroll-behavior: none` |
| Real browser history, so the Android back button works | React Router |
| A slow-server notice and an offline screen | `useServerStatus`, `OfflineState` |
| Fonts bundled, not fetched from a CDN | `@fontsource-variable/inter` |

Colours use `oklch()`, which needs a reasonably current Android System WebView. Median runs on the
phone's WebView, so check the device in Phase 1.

### Device check

- [ ] Sign in survives killing and reopening the app
- [ ] Camera capture and gallery upload both reach the backend (Phase 4)
- [ ] Android back follows screen history and does not exit unexpectedly
- [ ] Student and Technician workspaces fit at 360px with no sideways scroll
- [ ] The campus map pans and zooms by touch (Phase 3)
- [ ] Airplane mode shows the offline screen and recovers
- [ ] A web deploy appears in the app without reinstalling

## 9. Demo-day runbook

**T-24h:** move to an always-on backend, run the smoke tests, tag `demo-candidate`.

**T-1h:** open `/api/v1/system/ping` and check `database` says `UP`, reset to Scenario A (from
Phase 13), sign in as each demo role, and open the APK on phone data as well as venue Wi-Fi.

| Failure | Response |
|---|---|
| Gemini slow or down | Summaries fall back to the template automatically |
| AI misbehaving | Turn the feature flag off. Rule fallbacks keep every workflow running |
| Venue network fails | Use a phone hotspot |
| Render or Vercel outage | Run `dev_server.py` and `npm run dev` on a laptop |
| Bad data during the demo | One-click scenario reset |

Record a full backup video of the demo while everything is healthy.

## 10. CI

`.github/workflows/ci.yml` runs on every push and pull request:

| Job | Checks |
|---|---|
| Backend | `pytest` |
| Frontend | Typecheck, layer check, tests, production build |
| Contract | The generated API contract, mock fixtures and TypeScript types are current |
