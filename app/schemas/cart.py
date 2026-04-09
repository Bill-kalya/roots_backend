from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal

class CartItem(BaseModel):
    product_id: UUID
    name: str
    price: Decimal
    quantity: int
    image_url: str
    origin: str

class CartResponse(BaseModel):
    items: list[CartItem]
    total_items: int
    subtotal: Decimal

class CartItemUpdate(BaseModel):
    product_id: UUID
    quantity: int  # Absolute quantity, not increment