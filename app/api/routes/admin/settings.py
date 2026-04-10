from fastapi import APIRouter, Depends
from app.core.dependencies import require_admin
from app.models.user import User

router = APIRouter()

@router.get("/")
async def get_system_settings(
    current_user: User = Depends(require_admin)
):
    """Get system settings (Admin only)"""
    return {
        "maintenance_mode": False,
        "site_name": "Roots",
        "contact_email": "admin@roots.com"
    }

@router.put("/")
async def update_system_settings(
    current_user: User = Depends(require_admin)
):
    """Update system settings (Admin only)"""
    return {"message": "Settings updated"}