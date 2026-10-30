"""Exports what the frontend builds against, straight from the running backend code.

    python -m tools.contract          write the files
    python -m tools.contract --check  fail if the committed files are stale

Outputs, relative to the repo root:
  frontend/src/types/openapi.json              the OpenAPI schema (npm run gen:api turns it into types)
  frontend/src/mocks/fixtures/generated.json   per-role bootstrap, roles, users for the mock server

Because the fixtures come from the real navigation catalog and role seed, the mocks cannot drift
from the backend.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx
from datetime import date, timedelta
from mongomock_motor import AsyncMongoMockClient

from app.campus.seed import generate_campus
from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = "frontend/src/types/openapi.json"
FIXTURES_PATH = "frontend/src/mocks/fixtures/generated.json"
FIXED_TIME = "2026-01-01T00:00:00Z"
PASSWORD = "Unio@Demo2026"

ROLE_EMAILS = {
    "STUDENT": "student@unio.demo",
    "FACULTY": "faculty@unio.demo",
    "DEPARTMENT_MANAGER": "dept@unio.demo",
    "FACILITIES_ADMIN": "facilities@unio.demo",
    "PROCUREMENT_APPROVER": "procure@unio.demo",
    "TECHNICIAN": "tech@unio.demo",
    "SYSTEM_ADMIN": "sysadmin@unio.demo",
}


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _clean(document: dict[str, Any], keep: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Renames _id to id and drops internal fields, which is how the API will present documents."""
    result = {"id": document["_id"]}
    for key, value in document.items():
        if key in ("_id", "campusId") or (keep is not None and key not in keep):
            continue
        result[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return result


def campus_fixture() -> dict[str, Any]:
    """The fictional campus from the real generator, for the map and every screen that names a place."""
    anchor = date(2026, 1, 5)  # a Monday, so the exam lands on a Wednesday
    data = generate_campus(anchor)
    map_document = {key: value for key, value in data["campus_map"][0].items() if key != "_id"}
    asset_counts: dict[str, int] = {}
    for asset in data["assets"]:
        asset_counts[asset["buildingId"]] = asset_counts.get(asset["buildingId"], 0) + 1
    wednesday = anchor + timedelta(days=2)
    local = timedelta(hours=5, minutes=30)
    sessions = []
    for session in data["timetable_sessions"]:
        start = session["startAt"] + local
        if start.date() != wednesday:
            continue
        end = session["endAt"] + local
        sessions.append(
            {
                "id": session["_id"],
                "courseName": session["courseName"],
                "kind": session["kind"],
                "roomId": session["roomId"],
                "facultyId": session["facultyId"],
                "studentGroup": session["studentGroup"],
                "headcount": session["headcount"],
                "start": start.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
            }
        )
    stock: dict[str, int] = {}
    for balance in data["inventory_balances"]:
        stock[balance["itemId"]] = stock.get(balance["itemId"], 0) + balance["onHand"]
    return {
        "map": map_document,
        "buildings": [{**_clean(b), "assetCount": asset_counts.get(b["_id"], 0)} for b in data["buildings"]],
        "rooms": [_clean(r) for r in data["rooms"]],
        "keyAssets": [_clean(a) for a in data["assets"] if a["criticality"] >= 4],
        "technicians": [_clean(t) for t in data["technicians"]],
        "faculty": [_clean(f) for f in data["faculty"]],
        "groups": [_clean(g) for g in data["student_groups"]],
        "sessions": sessions,
        "items": [{**_clean(i), "onHand": stock.get(i["_id"], 0)} for i in data["inventory_items"]],
        "history": [_clean(h) for h in data["maintenance_history"]],
    }


async def build_contract() -> dict[str, str]:
    settings = Settings(
        _env_file=None, app_env="dev", demo_mode_enabled=True, demo_user_password=PASSWORD, outbox_enabled=False
    )
    app = create_app(settings, db=AsyncMongoMockClient()["contract"])
    fixtures: dict[str, Any] = {"bootstrap": {}, "campus": campus_fixture()}
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://contract") as client:
            fixtures["demoAccounts"] = (await client.get("/api/v1/auth/demo-accounts")).json()
            for role, email in ROLE_EMAILS.items():
                token = (await client.post("/api/v1/auth/demo-login", json={"email": email})).json()["accessToken"]
                headers = {"Authorization": f"Bearer {token}"}
                body = (await client.get("/api/v1/me/bootstrap", headers=headers)).json()
                body["serverTime"] = FIXED_TIME
                fixtures["bootstrap"][role] = body
                if role == "SYSTEM_ADMIN":
                    fixtures["roles"] = (await client.get("/api/v1/admin/roles", headers=headers)).json()
                    fixtures["permissions"] = (await client.get("/api/v1/admin/permissions", headers=headers)).json()
                    users = (await client.get("/api/v1/admin/users?size=100", headers=headers)).json()
                    for user in users["items"]:
                        user["lastLoginAt"] = None  # set by the logins above, so it is not deterministic
                    fixtures["users"] = users
        openapi = app.openapi()
    return {OPENAPI_PATH: json.dumps(openapi, indent=2, sort_keys=True) + "\n", FIXTURES_PATH: _dump(fixtures)}


def main(argv: list[str]) -> int:
    contract = asyncio.run(build_contract())
    if "--check" in argv:
        stale = [
            path for path, text in contract.items() if not (ROOT / path).exists() or (ROOT / path).read_text("utf-8") != text
        ]
        if stale:
            print("Stale (run: python -m tools.contract): " + ", ".join(stale))
            return 1
        print("Contract files are current.")
        return 0
    for path, text in contract.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
