import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient

from app.audit.router import router as audit_router
from app.bookings.router import router as bookings_router
from app.campus.router import router as campus_router
from app.cascade.router import router as cascade_router
from app.collision.router import router as collisions_router
from app.config import Settings, get_settings
from app.core import correlation, idempotency
from app.core.access import assert_all_routes_guarded
from app.core.correlation import CorrelationIdMiddleware
from app.core.errors import register_error_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.idempotency import IdempotencyMiddleware
from app.core.outbox import run_outbox_loop
from app.db import ensure_indexes
from app.files.router import router as files_router
from app.incidents.router import router as incidents_router
from app.services import build_services
from app.simulation.router import router as simulation_router
from app.system.router import reserved, router as system_router
from app.users.router import admin_router, auth_router, demo_router, me_router
from app.users.seed import seed_reference_data
from app.workorders.router import router as workorders_router


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation = correlation.correlation_id.get() or "-"
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(f, _CorrelationFilter) for handler in root.handlers for f in handler.filters):
        return
    if not root.handlers:
        logging.basicConfig(level=logging.INFO)
    for handler in root.handlers:
        handler.addFilter(_CorrelationFilter())
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(correlation)s] %(name)s: %(message)s"))


def create_app(settings: Settings | None = None, db: Any = None) -> FastAPI:
    """Builds the application. Pass db to run against a supplied database, as the tests do."""
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = None
        database = db
        if database is None:
            client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=8000)
            database = client[settings.mongodb_database]
        services = build_services(settings, database)
        app.state.services = services
        app.state.identity = services.identity
        app.state.db = database
        await ensure_indexes(database)
        await seed_reference_data(services)
        await services.sla.ensure_policies()
        await services.collisions.ensure_rules()
        await services.bookings.claim_sessions()
        outbox_task = None
        if settings.outbox_enabled:
            outbox_task = asyncio.create_task(run_outbox_loop(services.outbox, settings.outbox_poll_seconds))
        try:
            yield
        finally:
            if outbox_task:
                outbox_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await outbox_task
            if client is not None:
                await client.close()

    app = FastAPI(
        title="UNIO API",
        version="0.1.0",
        description="CampusOps: report once, understand the impact, validate the response, track it to closure.",
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    register_error_handlers(app)

    # Added innermost first: idempotency, security headers, correlation id, then CORS outermost.
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", idempotency.HEADER, correlation.HEADER],
        expose_headers=[correlation.HEADER, idempotency.REPLAY_HEADER],
        max_age=3600,
    )

    app.include_router(system_router)
    app.include_router(auth_router)
    if settings.demo_mode_enabled:
        app.include_router(demo_router)
    app.include_router(me_router)
    app.include_router(admin_router)
    app.include_router(audit_router)
    app.include_router(campus_router)
    app.include_router(incidents_router)
    app.include_router(collisions_router)
    app.include_router(bookings_router)
    app.include_router(workorders_router)
    app.include_router(cascade_router)
    app.include_router(simulation_router)
    app.include_router(files_router)
    app.include_router(reserved)
    assert_all_routes_guarded(app)
    return app
