from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.db.session import get_db
from app.core.dependencies import require_merchant
from app.models.user import User
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse
from app.services.product_service import ProductService

router = APIRouter()

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new product (Merchant only)"""
    # In production, you'd associate product with merchant
    # product_data.merchant_id = current_user.id
    
    new_product = Product(
        name=product_data.name,
        description=product_data.description,
        price=product_data.price,
        image_url=product_data.image_url,
        origin=product_data.origin,
        tag=product_data.tag,
        stock=product_data.stock,
        is_featured=product_data.is_featured,
        is_active=True
    )
    
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    
    return ProductResponse.model_validate(new_product)

@router.get("/", response_model=List[ProductResponse])
async def get_merchant_products(
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db)
):
    """Get merchant's products"""
    # Filter by merchant_id in production
    service = ProductService(db)
    from app.schemas.common import PaginationParams
    params = PaginationParams(page=1, limit=100)
    products, _ = await service.get_products(params)
    return [ProductResponse.model_validate(p) for p in products]

@router.put("/{product_id}")
async def update_merchant_product(
    product_id: UUID,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db)
):
    """Update merchant's product"""
    return {"message": f"Update product {product_id}"}

@router.delete("/{product_id}")
async def delete_merchant_product(
    product_id: UUID,
    current_user: User = Depends(require_merchant),
    db: AsyncSession = Depends(get_db)
):
    """Delete merchant's product"""
    return {"message": f"Delete product {product_id}"}