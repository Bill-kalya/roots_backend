from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.db.session import get_db
from app.core.dependencies import get_current_active_user, get_redis
from app.models.user import User
from app.services.order_service import OrderService
from app.services.cart_service import CartService
from app.schemas.order import OrderCreate

from redis import asyncio as aioredis


router = APIRouter()


class CheckoutRequest(BaseModel):
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    shipping_method: Optional[str] = None


@router.post("")
async def create_checkout_session(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Create a checkout session from the current cart."""
    cart_service = CartService(redis)
    cart = await cart_service.get_cart(current_user.id)

    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot checkout with empty cart"
        )

    from app.services.product_service import ProductService
    product_service = ProductService(db)

    for item in cart.items:
        product = await product_service.get_product_by_id(item.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {item.product_id} not found"
            )
        if item.quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only {product.stock} items available for {product.name}"
            )

    order_service = OrderService(db, redis)

    cart_items_dict = [
        {
            "product_id": str(item.product_id),
            "name": item.name,
            "price": float(item.price),
            "quantity": item.quantity,
            "image_url": item.image_url,
            "origin": item.origin,
        }
        for item in cart.items
    ]

    order_data = OrderCreate(
        shipping_address=payload.shipping_address,
        payment_method=payload.payment_method,
        shipping_method=payload.shipping_method,
    )

    try:
        order = await order_service.create_order(
            current_user.id,
            order_data,
            cart_items_dict,
        )
    except ValueError as e:
        detail = str(e)
        try:
            detail = json.loads(detail)
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)

    return {
        "order_id": order.get("order_id"),
        "status": "created",
        "message": "Order created. Proceed to payment.",
    }
