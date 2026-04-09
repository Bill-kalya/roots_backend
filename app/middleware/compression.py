"""
app/middleware/compression.py

Provides a @compress_response decorator for individual FastAPI route handlers.
Compresses JSON responses with gzip when the response body exceeds a configured
minimum size AND the client signals Accept-Encoding: gzip.

Usage:
    @router.post("/items")
    @compress_response(min_size=1024)
    async def update_cart_item(...):
        ...
"""

import gzip
import json
import logging
import functools
from typing import Callable, Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def compress_response(min_size: int = 1024) -> Callable:
    """
    Decorator factory that gzip-compresses a route's JSON response when:
      1. The serialised body is larger than `min_size` bytes, AND
      2. The client sends `Accept-Encoding: gzip`.

    Falls back to a plain JSONResponse when neither condition is met,
    so the decorator is always safe to apply.

    Args:
        min_size: Minimum response body size in bytes before compression
                  is attempted. Defaults to 1 KB.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Response:
            # FastAPI injects `request` as a keyword arg when declared
            # in the route signature; fall back to positional args.
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            result = await func(*args, **kwargs)

            # Only attempt compression for dict / Pydantic-model payloads.
            # If the handler already returned a Response object, leave it alone.
            if isinstance(result, Response):
                return result

            # Serialise to JSON bytes
            try:
                if hasattr(result, "model_dump"):
                    payload = result.model_dump(mode="json")
                elif hasattr(result, "dict"):          # Pydantic v1 compat
                    payload = result.dict()
                else:
                    payload = result

                body = json.dumps(payload, default=str).encode("utf-8")
            except Exception as exc:
                logger.warning("compress_response: serialisation failed (%s), skipping compression", exc)
                return JSONResponse(content=result)

            # Check whether the client accepts gzip and body meets threshold
            accept_encoding = ""
            if request is not None:
                accept_encoding = request.headers.get("accept-encoding", "")

            if len(body) >= min_size and "gzip" in accept_encoding.lower():
                compressed = gzip.compress(body, compresslevel=6)
                saving_pct = (1 - len(compressed) / len(body)) * 100
                logger.debug(
                    "compress_response: %d → %d bytes (%.1f%% saving)",
                    len(body), len(compressed), saving_pct,
                )
                return Response(
                    content=compressed,
                    media_type="application/json",
                    headers={
                        "Content-Encoding": "gzip",
                        "Content-Length": str(len(compressed)),
                        "Vary": "Accept-Encoding",
                    },
                )

            # No compression — return a standard JSON response
            return Response(
                content=body,
                media_type="application/json",
            )

        return wrapper
    return decorator