import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from pymongo import AsyncMongoClient

from app.config import Settings
from app.main import create_app
from app.services import Services

DEMO_PASSWORD = "Unio@Demo2026"

ROLE_EMAILS = {
    "STUDENT": "student@unio.demo",
    "FACULTY": "faculty@unio.demo",
    "DEPARTMENT_MANAGER": "dept@unio.demo",
    "FACILITIES_ADMIN": "facilities@unio.demo",
    "PROCUREMENT_APPROVER": "procure@unio.demo",
    "TECHNICIAN": "tech@unio.demo",
    "SYSTEM_ADMIN": "sysadmin@unio.demo",
}
ROLES = list(ROLE_EMAILS)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "dev",
        "demo_mode_enabled": True,
        "demo_user_password": DEMO_PASSWORD,
        "outbox_enabled": False,
        "seed_campus": False,
        "seed_story": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _database() -> tuple[Any, Any, str]:
    """A real MongoDB when MONGODB_TEST_URI is set, otherwise an in-memory mock."""
    uri = os.environ.get("MONGODB_TEST_URI")
    if uri:
        client = AsyncMongoClient(uri, tz_aware=True)
        name = f"unio_test_{uuid.uuid4().hex[:8]}"
        return client, client[name], name
    return None, AsyncMongoMockClient()["unio_test"], "unio_test"


@dataclass
class Env:
    app: Any
    db: Any
    client: httpx.AsyncClient
    services: Services
    _tokens: dict[str, str] = field(default_factory=dict)

    async def token(self, role: str) -> str:
        if role not in self._tokens:
            response = await self.client.post("/api/v1/auth/demo-login", json={"email": ROLE_EMAILS[role]})
            assert response.status_code == 200, response.text
            self._tokens[role] = response.json()["accessToken"]
        return self._tokens[role]

    async def headers(self, role: str, **extra: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self.token(role)}", **extra}

    async def call(self, role: str, method: str, path: str, headers: dict[str, str] | None = None, **kwargs: Any):
        merged = await self.headers(role, **(headers or {}))
        return await self.client.request(method, path, headers=merged, **kwargs)


@asynccontextmanager
async def open_env(**overrides: Any):
    client, database, name = _database()
    app = create_app(make_settings(**overrides), db=database)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield Env(app=app, db=database, client=http, services=app.state.services)
    if client is not None:
        await client.drop_database(name)
        await client.close()


@pytest_asyncio.fixture
async def env():
    async with open_env() as opened:
        yield opened


@pytest_asyncio.fixture(scope="module")
async def shared_env():
    """One app for a whole module, for read-only suites such as the permission matrix."""
    async with open_env() as opened:
        yield opened
