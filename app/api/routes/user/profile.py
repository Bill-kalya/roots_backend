from fastapi import APIRouter, Depends
from app.core.dependencies import require_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(require_user)
):
    """Get current user profile"""
    return UserResponse.model_validate(current_user)

@router.put("/me")
async def update_my_profile(
    current_user: User = Depends(require_user)
):
    """Update user profile"""
    return {"message": "Profile update - coming soon"}