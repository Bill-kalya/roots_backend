from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.security import decode_token, TokenBlacklist
from app.db.session import get_db
from app.models.user import User, UserRole
from app.cache.redis_manager import redis_manager
from redis import asyncio as aioredis

import logging

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# Initialize token blacklist
token_blacklist = TokenBlacklist(redis_manager._client) if redis_manager._client else None

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token with database validation"""
    
    if not credentials:
        return None
    
    token = credentials.credentials
    
    # Check if token is blacklisted
    if token_blacklist and await token_blacklist.is_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )
    
    # Decode token
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get user from database
    from uuid import UUID
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID"
        )
    
    query = select(User).where(User.id == user_uuid, User.is_active == True)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Verify role from token matches database (security)
    token_role = payload.get("role")
    if token_role != user.role.value:
        logger.warning(f"Role mismatch for user {user.email}: token={token_role}, db={user.role.value}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims"
        )
    
    return user

# Role-based access control decorators

async def require_any_user(current_user: User = Depends(get_current_user)) -> User:
    """Require authenticated user (any role)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user

async def require_user(current_user: User = Depends(get_current_user)) -> User:
    """Require USER role"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if current_user.role not in [UserRole.USER, UserRole.MERCHANT, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access required"
        )
    
    return current_user

async def require_merchant(current_user: User = Depends(get_current_user)) -> User:
    """Require MERCHANT role"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if current_user.role not in [UserRole.MERCHANT, UserRole.ADMIN]:
        logger.warning(f"Unauthorized merchant access attempt by {current_user.email} (role: {current_user.role.value})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant access required"
        )
    
    if current_user.role == UserRole.MERCHANT and not current_user.merchant_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Merchant account pending approval"
        )
    
    return current_user

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require ADMIN role"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if current_user.role != UserRole.ADMIN:
        logger.warning(f"Unauthorized admin access attempt by {current_user.email} (role: {current_user.role.value})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

# Optional: Rate limiting by role
async def get_rate_limit_config(user: Optional[User] = Depends(get_current_user)) -> dict:
    """Get rate limit config based on user role"""
    if not user:
        return {"requests": 50, "period": 60}  # Anonymous users
    
    if user.role == UserRole.ADMIN:
        return {"requests": 500, "period": 60}  # Admins: high limit
    elif user.role == UserRole.MERCHANT:
        return {"requests": 200, "period": 60}  # Merchants: medium limit
    else:
        return {"requests": 100, "period": 60}  # Regular users: standard limit


async def get_redis():
    """Get Redis client dependency"""
    return redis_manager._client


# Aliases for backwards compatibility
get_current_active_user = require_any_user
get_current_admin_user = require_admin
