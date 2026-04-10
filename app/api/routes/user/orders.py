from fastapi import APIRouter, Depends
from app.core.dependencies import require_user
from app.models.user import User

router = APIRouter()

@router.get("/")
async def get_my_orders(
    current_user: User = Depends(require_user)
):
    """Get user's order history"""
    return {"message": "User orders - coming soon"}