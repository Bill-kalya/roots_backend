from __future__ import annotations

import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException


def _make_serializable(obj):
    """Recursively make an object JSON-serializable.

    FastAPI/Pydantic validation errors can include raw request input (e.g. uploaded file bytes).
    Those bytes cannot be JSON-encoded; we replace them with a safe placeholder.
    """
    if isinstance(obj, bytes):
        return f"<bytes len={len(obj)}>"
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    return obj



logger = logging.getLogger(__name__)


def _json_error(request: Request, status_code: int, error: str, message: str, details=None):
    payload = {
        "error": error,
        "message": message,
        # IMPORTANT: frontend axios calls everywhere (Login.jsx, Register.jsx,
        # services/api.js) read err.response.data.detail. Without this key,
        # they silently fall back to the generic axios error string and never
        # see the real backend reason (wrong password, unverified email,
        # duplicate email, lockout, etc).
        "detail": message,
    }
    if details is not None:
        payload["details"] = _make_serializable(details)
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
    # Build a human-readable error message from validation errors
    errors = exc.errors()
    if errors:
        first_error = errors[0]
        field = ".".join(str(x) for x in first_error.get("loc", []))
        msg = first_error.get("msg", "Invalid input")
        # E.g. "email: value is not a valid email address" or "password: ensure this value has at least 8 characters"
        if field and field != "body":
            user_message = f"{field}: {msg}"
        else:
            user_message = msg
    else:
        user_message = "Request validation failed"
    
    return _json_error(
        request,
        status_code=422,
        error="validation_error",
        message=user_message,
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

