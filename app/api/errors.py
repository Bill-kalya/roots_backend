from __future__ import annotations

import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _json_error(request: Request, status_code: int, error: str, message: str, details=None):
    payload = {
        "error": error,
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    # Keep request_id in logs/clients via middleware header
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=payload)


async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.info(
        "Request validation failed",
        extra={"path": request.url.path, "errors": exc.errors()},
    )
    return _json_error(
        request,
        status_code=422,
        error="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP exception",
        extra={"path": request.url.path, "status_code": exc.status_code, "detail": exc.detail},
    )
    return _json_error(
        request,
        status_code=exc.status_code,
        error="http_error",
        message=str(exc.detail),
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    # For Starlette-level HTTP exceptions (often 404/405/413/etc.)
    logger.warning(
        "Starlette HTTP exception",
        extra={"path": request.url.path, "status_code": exc.status_code, "detail": getattr(exc, 'detail', None)},
    )
    return _json_error(
        request,
        status_code=exc.status_code,
        error="http_error",
        message=getattr(exc, "detail", "HTTP error"),
    )


async def global_exception_handler(request: Request, exc: Exception):
    # Never leak internal error messages to clients.
    logger.exception("Unhandled exception", extra={"path": request.url.path})
    return _json_error(
        request,
        status_code=500,
        error="internal_server_error",
        message="An unexpected error occurred",
    )

