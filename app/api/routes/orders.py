from fastapi import APIRouter, Depends, HTTPException, status, Query
import json
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.core.dependencies import get_current_active_user, get_redis, get_current_admin_user
from app.services.order_service import OrderService
from app.services.cart_service import CartService
from app.schemas.order import OrderCreate, OrderResponse, OrderListResponse

from app.models.user import User
from redis import asyncio as aioredis
from app.models.payment import Payment, PaymentStatus
from app.security.audit_log import audit_service

from app.services.mpesa_service import MpesaService
from app.services.paypal_service import PayPalService


router = APIRouter()

@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Create a new order from cart"""
    # Get current cart
    cart_service = CartService(redis)
    cart = await cart_service.get_cart(current_user.id)
    
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create order with empty cart"
        )
    
    # Check stock availability
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
    
    # Create order
    order_service = OrderService(db, redis)
    
    # Convert cart items to dict for order creation
    cart_items_dict = [
        {
            "product_id": str(item.product_id),
            "name": item.name,
            "price": float(item.price),
            "quantity": item.quantity,
            "image_url": item.image_url,
            "origin": item.origin
        }
        for item in cart.items
    ]
    
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

    # create_order returns a dict, not an ORM object — fetch the full record
    order_with_items = await order_service.get_order_with_items(order["order_id"])

    if not order_with_items:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Order was created but could not be retrieved"
        )

    order_obj = order_with_items["order"]

    return OrderResponse(
        id=order_obj.id,
        user_id=order_obj.user_id,
        status=order_obj.status.value,
        subtotal=order_obj.subtotal,
        shipping_fee=order_obj.shipping_fee,
        total=order_obj.total,
        created_at=order_obj.created_at,
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

@router.get("/", response_model=OrderListResponse)
async def get_user_orders(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get current user's orders"""
    order_service = OrderService(db, redis)
    orders = await order_service.get_user_orders(current_user.id)
    
    order_responses = []
    for order in orders:
        order_with_items = await order_service.get_order_with_items(order.id)
        order_responses.append(
            OrderResponse(
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
        )
    
    return OrderListResponse(
        items=order_responses,
        total=len(order_responses)
    )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get specific order by ID (owner or admin only)."""
    order_service = OrderService(db, redis)

    if current_user.is_admin:
        order_with_items = await order_service.get_order_with_items(order_id)
    else:
        order_with_items = await order_service.get_order_with_items_for_user(order_id, current_user.id)

    if not order_with_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

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

@router.patch("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Cancel an order (only if pending)"""
    from app.models.order import OrderStatus
    
    order_service = OrderService(db, redis)
    order = await order_service.cancel_order(
        order_id,
        current_user.id,
        reason="user_cancelled"
    )

    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return {"success": True, "message": "Order cancelled successfully"}