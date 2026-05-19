from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User, UserRole
from app.schemas.user import UserResponse
from pydantic import BaseModel
from app.services.auth_service import AuthService
from app.core.dependencies import get_redis



class RoleUpdate(BaseModel):
    role: str


router = APIRouter()

@router.get("")
@router.get("/")
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    """List all users (Admin only)"""
    query = select(User).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]

@router.patch("/{user_id}/role")
async def change_user_role(
    user_id: UUID,
    body: RoleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Change user role (Admin only)

    Permanent fix for role-change JWT mismatch:
    invalidate the user's existing sessions + refresh tokens so they are forced to re-login
    (and will receive a new access token containing the updated role claim).
    """
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = body.role

    if role.upper() not in ["USER", "MERCHANT", "ADMIN"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user.role = UserRole[role.upper()]

    # Keep merchant approval in sync with role
    if role.upper() == "MERCHANT":
        user.merchant_approved = True
    elif role.upper() == "USER":
        user.merchant_approved = False

    await db.commit()

    # Invalidate existing sessions/refresh tokens for this user.
    # AuthService handles the Redis session + refresh token cleanup.
    service = AuthService(db, redis)
    await service.logout_all_devices(user_id)

    return {
        "message": f"User role updated to {role}",
        "user_id": str(user_id),
        "requires_relogin": True,
        "sessions_invalidated": True,
    }


@router.patch("/{user_id}/toggle-status")
async def toggle_user_status(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Activate/deactivate user (Admin only)"""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = not user.is_active
    await db.commit()
    
    status_text = "activated" if user.is_active else "deactivated"
    return {"message": f"User {status_text}", "user_id": str(user_id)}