from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from typing import Optional
from jose import JWTError

from app.db.session import get_db
from app.core.config import settings
from app.core.security import decode_token
from app.models.user import User
from app.services.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

async def get_redis() -> aioredis.Redis:
    """Get Redis client from app state"""
    from app.main import app
    return app.state.redis

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token"""
    if not token:
        return None
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    from uuid import UUID
    try:
        user_id = UUID(user_id)
    except ValueError:
        return None
    
    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)
    
    if not user or not user.is_active:
        return None
    
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user or raise 401"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current admin user or raise 403"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

def cache_response(ttl: int = 300):
    """Decorator for caching API responses"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This is a placeholder - implement as needed
            return await func(*args, **kwargs)
        return wrapper
    return decorator