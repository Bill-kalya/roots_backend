from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional, Tuple, List
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
        query = select(Product).where(Product.is_active == True)
        
        # Apply filters
        if params.search:
            query = query.where(
                or_(
                    Product.name.ilike(f"%{params.search}%"),
                    Product.description.ilike(f"%{params.search}%")
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
        query = select(Product).where(
            Product.id == product_id,
            Product.is_active == True
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
