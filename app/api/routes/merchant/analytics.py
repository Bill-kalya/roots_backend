from fastapi import APIRouter, Depends
from app.core.dependencies import require_merchant
from app.models.user import User

router = APIRouter()

@router.get("/dashboard")
async def merchant_analytics(
    current_user: User = Depends(require_merchant)
):
    """Get merchant analytics dashboard"""
    return {
        "total_sales": 0,
        "total_orders": 0,
        "top_products": [],
        "revenue_chart": {}
    }