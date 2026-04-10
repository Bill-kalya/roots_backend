from fastapi import APIRouter, Depends
from app.core.dependencies import require_admin
from app.models.user import User

router = APIRouter()

@router.get("/pending")
async def get_pending_products(
    current_user: User = Depends(require_admin)
):
    """Get products pending approval (Admin only)"""
    return {"message": "Pending products - coming soon"}

@router.post("/{product_id}/approve")
async def approve_product(
    product_id: str,
    current_user: User = Depends(require_admin)
):
    """Approve product (Admin only)"""
    return {"message": f"Product {product_id} approved"}