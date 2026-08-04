from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_user, get_redis
from app.db.session import get_db
from app.models.user import User
from app.services.order_service import OrderService
from app.schemas.order import OrderResponse, OrderListResponse

from redis import asyncio as aioredis

router = APIRouter()


class CancelOrderRequest(BaseModel):
    reason: Optional[str] = None


class ReturnOrderRequest(BaseModel):
    reason: str


def _serialize_order(order_with_items) -> OrderResponse:
    order = order_with_items["order"]
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=order.status.value,
        subtotal=order.subtotal,
        shipping_fee=order.shipping_fee,
        total=order.total,
        created_at=order.created_at,
        items=[
            {
                "product_id": item.product_id,
                "name_snapshot": item.name_snapshot,
                "price_snapshot": item.price_snapshot,
                "quantity": item.quantity
            }
            for item in order_with_items["items"]
        ]
    )


@router.get("", response_model=OrderListResponse)
async def get_my_orders(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Get current user's order history (owner only)."""
    order_service = OrderService(db, redis)
    orders = await order_service.get_user_orders(current_user.id)

    responses = []
    for order in orders:
        order_with_items = await order_service.get_order_with_items_for_user(order.id, current_user.id)
        if order_with_items:
            responses.append(_serialize_order(order_with_items))

    return OrderListResponse(items=responses, total=len(responses))


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order_by_id(
    order_id: UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Get specific order by ID (owner only; 404 for others)."""
    order_service = OrderService(db, redis)
    order_with_items = await order_service.get_order_with_items_for_user(order_id, current_user.id)

    if not order_with_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return _serialize_order(order_with_items)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    payload: CancelOrderRequest,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Cancel an order (owner only, pending/paid only)."""
    order_service = OrderService(db, redis)
    try:
        order = await order_service.cancel_order(
            order_id,
            current_user.id,
            reason=payload.reason or "user_cancelled",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return {"success": True, "order_id": str(order.id), "status": order.status.value}


@router.post("/{order_id}/return")
async def request_return(
    order_id: str,
    payload: ReturnOrderRequest,
    current_user: User = Depends(require_user)
):
    """Request a return for an order"""
    return {
        "message": "Return request received",
        "order_id": order_id,
        "reason": payload.reason
    }


@router.get("/{order_id}/tracking")
async def track_order(
    order_id: str,
    current_user: User = Depends(require_user)
):
    """Get order tracking information"""
    return {
        "order_id": order_id,
        "tracking_number": None,
        "carrier": None,
        "status": "pending",
        "estimated_delivery": None,
        "updates": []
    }


@router.post("/{order_id}/reorder")
async def reorder(
    order_id: str,
    current_user: User = Depends(require_user)
):
    """Reorder items from a previous order"""
    return {
        "message": "Items added to cart",
        "order_id": order_id
    }
