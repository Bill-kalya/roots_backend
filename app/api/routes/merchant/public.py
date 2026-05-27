from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from uuid import UUID
import json

from app.db.session import get_db
from app.core.dependencies import get_redis
from app.models.user import User, UserRole
from app.models.product import Product

router = APIRouter()


@router.get("/{merchantId}", response_model=dict)
async def get_public_merchant(merchantId: str, db: AsyncSession = Depends(get_db), redis: aioredis.Redis = Depends(get_redis)):

    """Get merchant details by merchantId.

    Production contract:
    - Endpoint: GET /api/merchants/{merchantId}
    - Response: { "merchant": { "id": ..., "name": ... } }
    """
    try:
        merchant_uuid = UUID(merchantId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant ID")

    cache_key = f"merchant:{merchant_uuid}:public"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    merchant = await db.get(User, merchant_uuid)
    if not merchant or not merchant.is_active or merchant.role != UserRole.MERCHANT:
        raise HTTPException(status_code=404, detail="Merchant not found")

    name = merchant.store_name or merchant.full_name
    payload = {"merchant": {"id": str(merchant.id), "name": name}}

    await redis.setex(cache_key, 600, json.dumps(payload, default=str))
    return payload


@router.get("/products", response_model=dict)
async def get_public_merchant_products(
    merchantId: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """Get merchant products.

    Production contract:
    - Endpoint: GET /api/merchants/{merchantId}/products
    - Response shape: {"products": [ ... ]}
    - Each product includes: id, name, price, image_url
    """
    try:
        merchant_uuid = UUID(merchantId)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid merchant ID")

    cache_key = f"merchant:{merchant_uuid}:products:{limit}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Note: Product model must have products.merchant_id.
    if not hasattr(Product, "merchant_id"):
        raise HTTPException(status_code=500, detail="Product merchant linkage not configured")

    q = (
        db.query(Product) if hasattr(db, "query") else None
    )
    # AsyncSession doesn't have .query reliably; use SQLAlchemy select.
    from sqlalchemy import select

    stmt = (
        select(Product)
        .where(Product.merchant_id == merchant_uuid, Product.is_active.is_(True))
        .order_by(Product.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    items = [
        {
            "id": str(p.id),
            "name": p.name,
            "price": str(p.price),
            "image_url": p.image_url,
        }
        for p in products
    ]

    payload = {"products": items}
    await redis.setex(cache_key, 300, json.dumps(payload, default=str))
    return payload

