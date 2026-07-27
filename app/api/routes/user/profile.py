from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.dependencies import require_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(require_user)
):
    """Get current user profile"""
    return UserResponse.model_validate(current_user)


@router.put("/me")
async def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(require_user)
):
    """Update user profile"""
    return {"message": "Profile updated successfully"}


@router.patch("/me")
async def patch_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(require_user)
):
    """Patch user profile (partial update)"""
    return {"message": "Profile updated successfully"}
