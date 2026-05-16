from fastapi import APIRouter, Depends
from app.core.dependencies import require_merchant
from app.models.user import User

router = APIRouter()

@router.get("")
async def merchant_analytics_base(
    current_user: User = Depends(require_merchant),
):
    """Alias for GET /api/merchant/analytics"""
    return {
        "total_sales": 0,
        "total_orders": 0,
        "top_products": [],
        "revenue_chart": {}
    }


@router.get("/")
async def merchant_analytics_dashboard(
    current_user: User = Depends(require_merchant)
):
    """Get merchant analytics dashboard"""
    return {
        "total_sales": 0,
        "total_orders": 0,
        "top_products": [],
        "revenue_chart": {}
    }