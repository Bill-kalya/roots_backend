from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import hashlib
import json
from uuid import UUID

from app.db.session import get_db
from app.services.cart_service import CartService
from app.services.product_service import ProductService
from app.schemas.cart import CartResponse, CartItemUpdate
from app.core.dependencies import get_current_user, get_redis
from app.models.user import User
from redis import asyncio as aioredis
from app.core.validation import validate_request
from app.middleware.compression import compress_response

router = APIRouter()

def generate_etag(cart: CartResponse) -> str:
    """Generate ETag based on cart content"""
    content = f"{cart.total_items}:{cart.subtotal}:{hashlib.md5(str([(i.product_id, i.quantity) for i in cart.items]).encode()).hexdigest()}"
    return hashlib.md5(content.encode()).hexdigest()

@router.get("/", response_model=CartResponse)
async def get_cart(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    if_none_match: Optional[str] = None
):
    """Get current user's cart with ETag support"""
    
    service = CartService(redis)
    cart = await service.get_cart(current_user.id)
    
    # Generate ETag
    etag = generate_etag(cart)
    response.headers["ETag"] = etag
    
    # Check If-None-Match header
    if if_none_match and if_none_match == etag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return Response(content=None)
    
    # Add cache headers
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    response.headers["Vary"] = "Authorization"
    
    return cart

@router.post("/items", response_model=CartResponse)
@compress_response(min_size=1024)  # Compress responses larger than 1KB
async def update_cart_item(
    item: CartItemUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Update cart item quantity with validation"""
    
    # Input validation
    if item.quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity cannot be negative"
        )
    
    if item.quantity > 999:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity cannot exceed 999"
        )
    
    # Get product details
    product_service = ProductService(db)
    product = await product_service.get_product_by_id(item.product_id)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is no longer available"
        )
    
    if item.quantity > product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {product.stock} items available"
        )
    
    # Update cart in Redis
    cart_service = CartService(redis)
    product_data = {
        "name": product.name,
        "price": float(product.price),
        "image_url": product.image_url,
        "origin": product.origin
    }
    
    try:
        result = await cart_service.set_cart_item(
            current_user.id,
            item.product_id,
            item.quantity,
            product_data
        )
        
        # Add HATEOAS links
        response = result.dict()
        response["_links"] = {
            "self": {"href": f"/api/cart"},
            "checkout": {"href": "/api/orders", "method": "POST"},
            "product": {"href": f"/api/products/{item.product_id}"}
        }
        
        return response
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.delete("/items/{product_id}", response_model=CartResponse)
async def remove_cart_item(
    product_id: str,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Remove item from cart"""
    
    cart_service = CartService(redis)
    return await cart_service.remove_cart_item(current_user.id, UUID(product_id))

@router.post("/merge")
async def merge_anonymous_cart(
    anonymous_cart: dict,
    current_user: User = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Merge anonymous cart with user cart after login"""
    
    cart_service = CartService(redis)
    result = await cart_service.merge_carts(current_user.id, anonymous_cart)
    
    return {
        "success": True,
        "message": "Cart merged successfully",
        "cart": result
    }