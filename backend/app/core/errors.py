import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.correlation import correlation_id

log = logging.getLogger("unio.errors")


class ApiException(Exception):
    """A deliberate, user-facing failure. The single error shape is in docs/API_CONTRACT.md."""

    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def unauthenticated() -> ApiException:
    return ApiException(401, "UNAUTHENTICATED", "Please sign in to continue.")


def forbidden() -> ApiException:
    return ApiException(403, "PERMISSION_DENIED", "You do not have permission for this action.")


def not_found(what: str) -> ApiException:
    """Also used for rows outside the caller scope, so a 403 never confirms a row exists."""
    return ApiException(404, "NOT_FOUND", f"{what} was not found.")


def conflict(code: str, message: str) -> ApiException:
    return ApiException(409, code, message)


def rule(code: str, message: str) -> ApiException:
    return ApiException(422, code, message)


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details or {}, "correlationId": correlation_id.get()}


def respond(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, details))


_HTTP_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHENTICATED", 403: "PERMISSION_DENIED"}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def _api(_: Request, exc: ApiException) -> JSONResponse:
        return respond(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": ".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return respond(400, "VALIDATION_FAILED", "Please check the highlighted fields.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        message = "This resource was not found." if exc.status_code == 404 else str(exc.detail)
        return respond(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled request failure", exc_info=exc)
        return respond(500, "INTERNAL_ERROR", "Something went wrong on our side.")
