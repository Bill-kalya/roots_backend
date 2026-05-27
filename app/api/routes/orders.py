from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    
    order = await order_service.create_order(
        current_user.id,
        order_data,
        cart_items_dict
    )
    
    # Get order with items
    order_with_items = await order_service.get_order_with_items(order.id)
    
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
    """Get specific order by ID"""
    order_service = OrderService(db, redis)
    order_with_items = await order_service.get_order_with_items(order_id)
    
    if not order_with_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    order = order_with_items["order"]
    
    # Check ownership (allow admin to view any order)
    if str(order.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
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