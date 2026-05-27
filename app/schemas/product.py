from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional


class ProductBase(BaseModel):
    name: str
    description: str
    long_description: Optional[str] = None
    price: Decimal
    image_url: str
    gallery: list[str] = []
    origin: str
    tag: Optional[str] = None
    stock: int
    artisan: Optional[str] = None
    weight: Optional[str] = None
    dimensions: Optional[str] = None
    year: Optional[int] = None
    materials: list[str] = []

    @field_validator("materials", "gallery", mode="before")
    @classmethod
    def coerce_array(cls, v):
        return v if v is not None else []


class ProductCreate(ProductBase):
    is_featured: bool = False


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    long_description: Optional[str] = None
    price: Optional[Decimal] = None
    image_url: Optional[str] = None
    gallery: Optional[list[str]] = None
    origin: Optional[str] = None
    tag: Optional[str] = None
    stock: Optional[int] = None
    artisan: Optional[str] = None
    weight: Optional[str] = None
    dimensions: Optional[str] = None
    year: Optional[int] = None
    materials: Optional[list[str]] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None


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
