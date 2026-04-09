from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import List, Optional

class OrderItemBase(BaseModel):
    product_id: UUID
    name_snapshot: str
    price_snapshot: Decimal
    quantity: int

class OrderCreate(BaseModel):
    shipping_fee: Decimal = Decimal("0.00")

class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    subtotal: Decimal
    shipping_fee: Decimal
    total: Decimal
    created_at: datetime
    items: List[OrderItemBase]

class OrderListResponse(BaseModel):
    items: List[OrderResponse]
    total: int