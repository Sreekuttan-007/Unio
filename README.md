# UNIO

UNIO is a campus operations application with a React frontend and a FastAPI backend. It includes role-based workspaces, audit and access controls, and a mock-data mode for frontend development.

## Local development

Requirements: Python 3.12+, Node.js 22+, and npm.

Start the backend in one terminal (demo accounts and in-memory data):

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe dev_server.py
```

Start the frontend in another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The API runs at [http://localhost:8000](http://localhost:8000).
The development backend uses an in-memory database; its data resets when it stops.

To run the frontend with mock API responses instead:

```powershell
cd frontend
npm ci
npm run dev:mock
```

For a local MongoDB-backed API, start Docker Desktop and run `docker compose up --build` from the repository root.

## Checks

```powershell
# Backend
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m tools.contract --check

# Frontend
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for environment configuration and deployment notes. Other design references are in [docs/](docs/).
