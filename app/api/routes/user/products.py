from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.core.dependencies import require_user
from app.models.user import User
from app.services.product_service import ProductService
from app.schemas.product import ProductResponse

router = APIRouter()

@router.get("/", response_model=List[ProductResponse])
async def get_user_products(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db)
):
    """Get products for regular users (filtered, safe)"""
    service = ProductService(db)
    # Users can only see active, approved products
    from app.schemas.common import PaginationParams
    params = PaginationParams(page=1, limit=50)
    products, _ = await service.get_products(params)
    return [ProductResponse.model_validate(p) for p in products]

@router.get("/favorites")
async def get_user_favorites(
    current_user: User = Depends(require_user)
):
    """Get user's favorite products"""
    return {"message": "User favorites - coming soon"}