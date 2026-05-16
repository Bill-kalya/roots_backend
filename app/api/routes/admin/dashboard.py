from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_admin
from app.db.session import get_db
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User

router = APIRouter()


@router.get("/stats")
async def admin_stats(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get admin dashboard statistics."""

    order_revenue_statuses = ["paid", "delivered", "shipped"]

    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    total_products = await db.scalar(select(func.count()).select_from(Product)) or 0
    total_orders = await db.scalar(select(func.count()).select_from(Order)) or 0

    pending_orders = (
        await db.scalar(
            select(func.count()).select_from(Order).where(Order.status == "pending")
        )
        or 0
    )

    low_stock = (
        await db.scalar(
            select(func.count()).select_from(Product).where(Product.stock_quantity <= 5)
        )
        or 0
    )

    total_sales = (
        await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status.in_(order_revenue_statuses)
            )
        )
        or 0
    )

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)

    this_month_revenue = (
        await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.created_at >= month_start,
                Order.created_at < (month_start + timedelta(days=31)),
                Order.status.in_(order_revenue_statuses),
            )
        )
        or 0
    )

    prev_month_revenue = (
        await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.created_at >= prev_month_start,
                Order.created_at < month_start,
                Order.status.in_(order_revenue_statuses),
            )
        )
        or 0
    )

    this_month_orders = (
        await db.scalar(
            select(func.count()).select_from(Order).where(Order.created_at >= month_start)
        )
        or 0
    )

    prev_month_orders = (
        await db.scalar(
            select(func.count()).select_from(Order).where(
                Order.created_at >= prev_month_start, Order.created_at < month_start
            )
        )
        or 0
    )

    def growth_pct(current: float, previous: float) -> float:
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    top_products_rows = (
        await db.execute(
            select(
                Product.name.label("product_name"),
                func.sum(OrderItem.quantity).label("units_sold"),
            )
            .join(OrderItem, OrderItem.product_id == Product.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.status.in_(order_revenue_statuses))
            .group_by(Product.id, Product.name)
            .order_by(desc("units_sold"))
            .limit(5)
        )
    ).fetchall()

    top_products = [
        {"name": row.product_name, "units_sold": int(row.units_sold)}
        for row in top_products_rows
    ]

    sales_by_day = {"labels": [], "values": []}
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_total = (
            await db.scalar(
                select(func.coalesce(func.sum(Order.total), 0)).where(
                    Order.created_at >= day_start,
                    Order.created_at < day_end,
                    Order.status.in_(order_revenue_statuses),
                )
            )
            or 0
        )

        sales_by_day["labels"].append(day.strftime("%a"))
        sales_by_day["values"].append(float(day_total))

    return {
        "total_sales": float(total_sales),
        "total_orders": int(total_orders),
        "total_users": int(total_users),
        "total_products": int(total_products),
        "pending_orders": int(pending_orders),
        "low_stock": int(low_stock),
        "revenue_growth": growth_pct(float(this_month_revenue), float(prev_month_revenue)),
        "order_growth": growth_pct(float(this_month_orders), float(prev_month_orders)),
        "top_products": top_products,
        "sales_by_day": sales_by_day,
        "maintenance_mode": False,
    }


@router.get("/orders")
async def admin_orders(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get recent orders for the admin dashboard."""

    rows = (
        await db.execute(
            select(Order).order_by(desc(Order.created_at)).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [
            {
                "id": str(order.id),
                "customer_name": getattr(order, "customer_name", "—"),
                "total": float(order.total),
                "status": order.status.value if hasattr(order.status, "value") else order.status,
                "created_at": order.created_at.isoformat(),
            }
            for order in rows
        ],
        "total": len(rows),
    }


@router.get("/recent-activity")
async def recent_activity(
    current_user: User = Depends(require_admin),
):
    """Get recent system activity."""

    return {"message": "Recent activity log - coming soon"}

