from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID


PaymentMethod = Literal["mpesa", "paypal"]


class DeliveryInfo(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=30)
    address: str = Field(..., min_length=5, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    country: str = Field(..., min_length=2, max_length=100)


class CheckoutRequest(BaseModel):
    payment_method: PaymentMethod
    delivery: DeliveryInfo

    # Provider-specific optional fields
    mpesa_phone: Optional[str] = Field(
        default=None,
        description="Required for M-Pesa. Use international format depending on Daraja config.",
    )

    # PayPal
    cancel_url: Optional[str] = None
    success_url: Optional[str] = None


class CheckoutResponse(BaseModel):
    order_id: UUID
    status: str
    total: Decimal
    payment_method: PaymentMethod

    # Provider session/redirect info
    provider: str
    redirect_url: Optional[str] = None
    reference: Optional[str] = None

