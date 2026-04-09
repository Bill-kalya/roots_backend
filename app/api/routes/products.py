from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from redis import asyncio as aioredis
from app.db.session import get_db
from app.services.product_service import ProductService
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.common import PaginationParams
from app.core.dependencies import get_redis
from uuid import UUID
import json

router = APIRouter()

@router.get("/", response_model=ProductListResponse)
async def get_products(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    search: str = None,
    tag: str = None,
    origin: str = None,
    sort: str = None,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get all products with filtering and pagination"""
    # Try cache for first page with no filters
    cache_key = f"products:list:{page}:{limit}:{search}:{tag}:{origin}:{sort}"
    cached = await redis.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    params = PaginationParams(
        page=page,
        limit=limit,
        search=search,
        tag=tag,
        origin=origin,
        sort=sort
    )
    
    service = ProductService(db)
    products, total = await service.get_products(params)
    
    # Convert to response models
    items = [ProductResponse.model_validate(p) for p in products]
    
    response = ProductListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=(total + limit - 1) // limit
    )
    
    # Cache for 5 minutes
    await redis.setex(cache_key, 300, json.dumps(response.model_dump(), default=str))
    
    return response

@router.get("/featured", response_model=list[ProductResponse])
async def get_featured_products(
    limit: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get featured products"""
    cache_key = f"products:featured:{limit}"
    cached = await redis.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    service = ProductService(db)
    products = await service.get_featured_products(limit)
    
    response = [ProductResponse.model_validate(p) for p in products]
    
    # Cache for 10 minutes
    await redis.setex(cache_key, 600, json.dumps([p.model_dump() for p in response], default=str))
    
    return response

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis)
):
    """Get single product by ID"""
    cache_key = f"product:{product_id}"
    cached = await redis.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    try:
        product_uuid = UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    
    service = ProductService(db)
    product = await service.get_product_by_id(product_uuid)
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    response = ProductResponse.model_validate(product)
    
    # Cache for 1 hour
    await redis.setex(cache_key, 3600, json.dumps(response.model_dump(), default=str))
    
    return response