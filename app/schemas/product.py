from pydantic import BaseModel, ConfigDict
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional

class ProductBase(BaseModel):
    name: str
    description: str
    price: Decimal
    image_url: str
    origin: str
    tag: Optional[str] = None
    stock: int

class ProductCreate(ProductBase):
    is_featured: bool = False

class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_featured: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    limit: int
    pages: int