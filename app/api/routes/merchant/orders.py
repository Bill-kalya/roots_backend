from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from uuid import UUID
from typing import List

from app.core.dependencies import require_merchant
from app.db.session import get_db
from app.models.user import User
from app.models.order import Order, OrderItem

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def _merchant_product_filters(current_user: User):
    """Return an optional SQLAlchemy filter condition for merchant ownership.

    The current codebase/models may or may not expose a Product.merchant_id.
    We keep this as best-effort to avoid breaking when the relationship isn't present.

    If we can't determine merchant->product ownership, we return None.
    """
    try:
        from app.models.product import Product  # local import

        if hasattr(Product, "merchant_id"):
            # Orders are merchant-visible if they contain OrderItem whose Product belongs to merchant.
            return Product
    except Exception:
        pass

    return None


@router.get("")
@router.get("/")
async def get_merchant_orders(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
):
    """Get merchant orders.

    Returns an array (not a placeholder object) as expected by the frontend.

    Response shape is a best-effort list of orders with their items.
    """

    Product = _merchant_product_filters(current_user)
    if Product is None:
        # Can't reliably filter merchant ownership with current schema.
        return []

    # Get order IDs that have merchant-owned products.
    order_ids_stmt = (
        select(distinct(Order.id))
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Product.merchant_id == current_user.id)
    )

    result = await db.execute(order_ids_stmt)
    order_ids = [row[0] for row in result.all()]

    if not order_ids:
        return []

    orders_stmt = (
        select(Order)
        .where(Order.id.in_(order_ids))
        .order_by(Order.created_at.desc())
    )
    orders_result = await db.execute(orders_stmt)
    orders: List[Order] = list(orders_result.scalars().all())

    items_stmt = select(OrderItem).where(OrderItem.order_id.in_([o.id for o in orders]))
    items_result = await db.execute(items_stmt)
    all_items: List[OrderItem] = list(items_result.scalars().all())

    items_by_order = {}
    for it in all_items:
        items_by_order.setdefault(it.order_id, []).append(it)

    resp = []
    for o in orders:
        resp.append(
            {
                "id": o.id,
                "user_id": o.user_id,
                "status": o.status.value if hasattr(o.status, "value") else str(o.status),
                "subtotal": float(o.subtotal),
                "shipping_fee": float(o.shipping_fee),
                "total": float(o.total),
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": [
                    {
                        "product_id": it.product_id,
                        "name_snapshot": it.name_snapshot,
                        "price_snapshot": float(it.price_snapshot),
                        "quantity": it.quantity,
                    }
                    for it in items_by_order.get(o.id, [])
                ],
            }
        )

    return resp


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: str,
    request: Request,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db),
    new_status_str: str = Query("SHIPPED", alias="status"),
):
    """Update order status."""
    from app.models.order import OrderStatus

    try:
        new_status = OrderStatus(new_status_str.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {new_status_str}. Must be one of: shipped, delivered, cancelled",
        )

    valid_transitions = {OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED}
    if new_status not in valid_transitions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition to {new_status_str}. Allowed: shipped, delivered, cancelled",
        )

    try:
        order_uuid = UUID(order_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid order_id",
        )

    order = (await db.execute(select(Order).where(Order.id == order_uuid))).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Verify merchant owns at least one product in the order
    from app.models.product import Product
    ownership_stmt = (
        select(OrderItem.id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order.id, Product.merchant_id == current_user.id)
        .limit(1)
    )
    ownership_result = await db.execute(ownership_stmt)
    if not ownership_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own any products in this order",
        )

    order.status = new_status

    if new_status == OrderStatus.CANCELLED:
        from app.models.payment import Payment, PaymentStatus
        payment_stmt = select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.COMPLETED.value)
        payment_res = await db.execute(payment_stmt)
        payment = payment_res.scalar_one_or_none()
        if payment:
            payment.status = PaymentStatus.CANCELLED.value

    await db.commit()
    await db.refresh(order)

    return {"success": True, "id": str(order.id), "status": order.status.value}

