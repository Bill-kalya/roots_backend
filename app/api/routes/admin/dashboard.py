from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.product import Product
from app.models.order import Order

router = APIRouter()

@router.get("/stats")
async def admin_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics"""
    
    # Get user counts
    total_users = await db.scalar(select(func.count()).select_from(User))
    total_merchants = await db.scalar(
        select(func.count()).select_from(User).where(User.role == "MERCHANT")
    )
    total_admins = await db.scalar(
        select(func.count()).select_from(User).where(User.role == "ADMIN")
    )
    
    # Get product counts
    total_products = await db.scalar(select(func.count()).select_from(Product))
    active_products = await db.scalar(
        select(func.count()).select_from(Product).where(Product.is_active == True)
    )
    
    return {
        "users": {
            "total": total_users,
            "merchants": total_merchants,
            "admins": total_admins
        },
        "products": {
            "total": total_products,
            "active": active_products
        },
        "system": {
            "status": "operational",
            "version": "2.0.0"
        }
    }

@router.get("/recent-activity")
async def recent_activity(
    current_user: User = Depends(require_admin)
):
    """Get recent system activity"""
    return {"message": "Recent activity log - coming soon"}