from fastapi import APIRouter, Depends
from app.core.dependencies import require_merchant
from app.models.user import User

router = APIRouter()

@router.get("")
@router.get("/")
async def get_merchant_orders(
    current_user: User = Depends(require_merchant),
):
    """Get orders for merchant's products"""
    return {"message": "Merchant orders - coming soon"}

@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    current_user: User = Depends(require_merchant)
):
    """Update order status"""
    return {"message": f"Update order {order_id} status"}

