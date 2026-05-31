from pydantic import BaseModel, Field
from decimal import Decimal
from uuid import UUID
from typing import Literal, Optional


class PayPalCreateOrderRequest(BaseModel):
    order_id: UUID
    amount: Decimal = Field(..., gt=0)
    currency: Literal["USD"] = "USD"


class PayPalCreateOrderResponse(BaseModel):
    approval_url: str
    paypal_order_id: str


class PayPalCaptureRequest(BaseModel):
    order_id: UUID
    paypal_order_id: str = Field(..., min_length=1)


class PayPalCaptureResponse(BaseModel):
    success: bool
    order_status: str
    paypal_order_id: str
    capture_id: Optional[str] = None

