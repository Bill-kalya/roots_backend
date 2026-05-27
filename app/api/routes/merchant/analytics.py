from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Dict, Any

from app.core.dependencies import require_merchant
from app.db.session import get_db
from app.models.user import User
from app.models.order import Order, OrderItem

router = APIRouter()


@router.get("")
@router.get("/")
async def merchant_analytics_dashboard(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Merchant analytics.

    Frontend cards expect:
      analytics.totalSales, analytics.totalOrders, analytics.totalRevenue,
      analytics.activeProducts, analytics.topProducts, analytics.revenueChart

    The task report indicates a mismatch between snake_case and camelCase.
    This endpoint returns camelCase directly.
    """

    # Best-effort: if Product.merchant_id exists, we can properly scope.
    # Otherwise, return safe zeros.
    try:
        from app.models.product import Product

        has_merchant_scope = hasattr(Product, "merchant_id")
    except Exception:
        has_merchant_scope = False

    if not has_merchant_scope:
        return {
            "totalSales": 0,
            "totalOrders": 0,
            "totalRevenue": 0,
            "activeProducts": 0,
            "topProducts": [],
            "revenueChart": {},
        }

    revenue_stmt = (
        select(func.coalesce(func.sum(Order.total), 0))
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.merchant_id == current_user.id)
    )

    total_orders_stmt = (
        select(func.count(func.distinct(Order.id)))
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.merchant_id == current_user.id)
    )

    active_products_stmt = (
        select(func.count(func.distinct(OrderItem.product_id)))
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.merchant_id == current_user.id)
    )

    top_products_stmt = (
        select(
            OrderItem.product_id,
            func.sum(OrderItem.quantity).label("qty"),
        )
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.merchant_id == current_user.id)
        .group_by(OrderItem.product_id)
        .order_by(desc("qty"))
        .limit(5)
    )

    revenue = (await db.execute(revenue_stmt)).scalar_one()
    total_orders = (await db.execute(total_orders_stmt)).scalar_one()
    active_products = (await db.execute(active_products_stmt)).scalar_one()

    top_products_rows = (await db.execute(top_products_stmt)).all()
    top_products = [
        {"productId": str(pid), "quantity": int(qty)} for pid, qty in top_products_rows
    ]

    revenue_chart: Dict[str, Any] = {}

    return {
        "totalSales": float(revenue),
        "totalOrders": int(total_orders),
        "totalRevenue": float(revenue),
        "activeProducts": int(active_products),
        "topProducts": top_products,
        "revenueChart": revenue_chart,
    }


