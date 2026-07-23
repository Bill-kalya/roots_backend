from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import joinedload, selectinload
from typing import Optional, Tuple, List
from uuid import UUID
from app.models.product import Product
from app.schemas.product import ProductListResponse, ProductResponse
from app.schemas.common import PaginationParams

class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_products(
        self, 
        params: PaginationParams
    ) -> Tuple[List[Product], int]:
        """Get products with filtering and pagination"""
        query = (
            select(Product)
            .options(selectinload(Product.merchant))
            .where(Product.is_active == True)
        )
        
        # Apply filters
        if params.search:
            query = query.where(
                or_(
                    Product.name.ilike(f"%{params.search}%"),
                    Product.description.ilike(f"%{params.search}%"),
                    Product.long_description.ilike(f"%{params.search}%"),
                    Product.artisan.ilike(f"%{params.search}%"),
                    Product.materials.ilike(f"%{params.search}%"),
                    Product.origin.ilike(f"%{params.search}%"),
                )
            )
        
        if params.tag:
            query = query.where(Product.tag == params.tag)
        
        if params.origin:
            query = query.where(Product.origin == params.origin)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Apply sorting
        if params.sort:
            if params.sort == "price_asc":
                query = query.order_by(Product.price.asc())
            elif params.sort == "price_desc":
                query = query.order_by(Product.price.desc())
            elif params.sort == "newest":
                query = query.order_by(Product.created_at.desc())
            else:
                query = query.order_by(Product.created_at.desc())
        else:
            query = query.order_by(Product.created_at.desc())
        
        # Apply pagination
        offset = (params.page - 1) * params.limit
        query = query.offset(offset).limit(params.limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        return products, total
    
    async def get_featured_products(self, limit: int = 6) -> List[Product]:
        """Get featured products"""
        query = select(Product).where(
            Product.is_active == True,
            Product.is_featured == True
        ).order_by(Product.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_product_by_id(self, product_id) -> Optional[Product]:
        """Get single product by ID"""
        query = (
            select(Product)
            .options(joinedload(Product.merchant))
            .where(
                Product.id == product_id,
                Product.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    
    async def get_products_by_tag(self, tag: str, limit: int = 20) -> List[Product]:
        """Get products by tag for cache warming"""
        query = select(Product).where(
            Product.is_active == True,
            Product.tag == tag
        ).order_by(Product.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_merchant_products(
        self,
        merchant_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 100,
    ) -> Tuple[List[Product], int]:
        """Get products for a specific merchant with optional status filter.
        
        Args:
            merchant_id: The merchant's user ID
            status: Optional filter - "active" for active products only, None for all
            page: Page number (1-indexed)
            limit: Items per page (max 100)
            
        Returns:
            Tuple of (products list, total count)
        """
        # Base query scoped to merchant
        query = select(Product).where(Product.merchant_id == merchant_id)
        
        # Apply optional status filter
        if status == "active":
            query = query.where(Product.is_active.is_(True))
        
        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        
        # Apply sorting and pagination
        query = query.order_by(Product.created_at.desc())
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        return products, total
