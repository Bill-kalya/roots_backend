from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal


class MerchantPayoutSettingsResponse(BaseModel):
    payout_method: Literal["MPESA", "PAYPAL", "STRIPE"]
    mpesa_phone: Optional[str]
    paypal_email: Optional[str] = None
    stripe_account_id: Optional[str] = None
    is_verified: bool
    supported_methods: List[Literal["MPESA", "PAYPAL", "STRIPE"]] = Field(
        default_factory=lambda: ["MPESA", "PAYPAL", "STRIPE"]
    )


class MerchantPayoutSettingsUpdateRequest(BaseModel):
    payout_method: Literal["MPESA", "PAYPAL", "STRIPE"]
    mpesa_phone: Optional[str] = None
    paypal_email: Optional[EmailStr] = None
    stripe_account_id: Optional[str] = None


class MerchantEarningsResponse(BaseModel):
    available_balance: float
    pending_balance: float
    currency: str

