from pydantic import BaseModel, Field
from uuid import UUID
from decimal import Decimal
from typing import Optional

class CartItem(BaseModel):
    product_id: UUID
    name: str
    price: Decimal
    quantity: int
    image_url: str
    origin: str
    merchant_id: Optional[UUID] = None

class CartResponse(BaseModel):
    items: list[CartItem]
    total_items: int
    subtotal: Decimal

class CartItemUpdate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=0, le=999)  # Absolute quantity, not increment