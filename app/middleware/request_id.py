from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4
from app.core.logging import request_id_var

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to every request"""
    
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request_id_var.set(request_id)
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response