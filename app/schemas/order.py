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
    # Shipping fee is the only field used by the current OrderService implementation.
    # We extend this schema to carry checkout details so POST /api/orders can
    # initialize payments server-side.
    shipping_fee: Decimal = Decimal("0.00")

    # Checkout fields (server-side use only; frontend must not be price-authoritative).
    payment_method: str  # "mpesa" | "paypal"
    delivery: dict

    # M-Pesa
    mpesa_phone: str | None = None

    # PayPal
    cancel_url: str | None = None
    success_url: str | None = None

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