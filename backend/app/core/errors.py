"""One error shape for the whole API: {code, message, details, request_id}."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(HTTPException):
    """Raise this from services: AppError(404, "not_found", "Product not found")."""

    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


def _body(request: Request, code: str, message: str, details=None) -> dict:
    return {
        "code": code,
        "message": message,
        "details": details or {},
        "request_id": getattr(request.state, "request_id", None),
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status_code)

    # Starlette's base class also covers 404s for unknown URLs and bad JSON bodies.
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(request, f"http_{exc.status_code}", str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = {".".join(str(p) for p in e["loc"][1:]): e["msg"] for e in exc.errors()}
        return JSONResponse(_body(request, "validation_error", "Please check the highlighted fields.", fields), status_code=422)

    # Two clicks at the same moment (check-in, same board code, same holiday): the database's
    # unique rule stops the second one. That's "already done", not a server bug.
    @app.exception_handler(IntegrityError)
    async def conflict(request: Request, exc: IntegrityError):
        # Only a unique rule (Postgres code 23505) means "already done". Any other broken rule
        # (missing link, empty required field) is a bug in our code and must show up as a 500.
        if _sqlstate(exc) != "23505":
            return await unexpected(request, exc)
        log.warning("db.conflict", extra={"request_id": getattr(request.state, "request_id", None),
                                          "reason": str(exc.orig)[:200]})
        return JSONResponse(_body(request, "conflict", "This was already done or already exists. Please refresh."),
                            status_code=409)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        # Logged once, here, with the stack trace. (request_id passed explicitly: this handler
        # runs outside the request middleware.)
        rid = getattr(request.state, "request_id", None)
        log.exception("server.error", extra={"request_id": rid})
        # The header too (the middleware never sees this response), so support can find the log line.
        return JSONResponse(_body(request, "server_error", "Something went wrong on our side."), status_code=500,
                            headers={"x-request-id": rid} if rid else None)


def _sqlstate(exc: IntegrityError) -> str | None:
    """Postgres error code of a database error ('23505' = unique rule broken)."""
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(getattr(orig, "__cause__", None), "sqlstate", None)
