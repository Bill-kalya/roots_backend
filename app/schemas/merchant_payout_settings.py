from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Literal


class MerchantPayoutSettingsResponse(BaseModel):
    payout_method: Literal["MPESA", "PAYPAL", "STRIPE"]
    mpesa_mode: Literal["PHONE", "TILL", "POCHI"]
    mpesa_phone: Optional[str]
    mpesa_till_number: Optional[str]
    pochi_phone: Optional[str]
    paypal_email: Optional[str] = None
    stripe_account_id: Optional[str] = None
    is_verified: bool
    supported_methods: List[Literal["MPESA", "PAYPAL", "STRIPE"]] = Field(
        default_factory=lambda: ["MPESA", "PAYPAL", "STRIPE"]
    )


class MerchantPayoutSettingsUpdateRequest(BaseModel):
    payout_method: Literal["MPESA", "PAYPAL", "STRIPE"]
    mpesa_mode: Optional[Literal["PHONE", "TILL", "POCHI"]] = None
    mpesa_phone: Optional[str] = None
    mpesa_till_number: Optional[str] = None
    pochi_phone: Optional[str] = None
    paypal_email: Optional[EmailStr] = None
    stripe_account_id: Optional[str] = None

    @classmethod
    def _validate_phone(cls, raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        n = raw.strip().replace("+", "").replace(" ", "").replace("-", "")
        if n.startswith("0"):
            n = "254" + n[1:]
        # Safaricom: 2547XXXXXXXX (12 digits, starts with 2547)
        if not (n.startswith("2547") and n.isdigit() and len(n) == 12):
            raise ValueError("Phone must be in format 2547XXXXXXXX")
        return n

    @classmethod
    def _validate_till(cls, raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        v = raw.strip()
        if not v.isdigit() or not (5 <= len(v) <= 10):
            raise ValueError("Till number must be 5-10 digits")
        return v

    def model_post_init(self, __context) -> None:
        # Pydantic v2 validation hook.
        if self.payout_method != "MPESA":
            return

        mode = self.mpesa_mode or "PHONE"

        phone = self._validate_phone(self.mpesa_phone) if mode == "PHONE" else None
        till = self._validate_till(self.mpesa_till_number) if mode == "TILL" else None
        pochi = self._validate_phone(self.pochi_phone) if mode == "POCHI" else None

        if mode == "PHONE" and not phone:
            raise ValueError("mpesa_phone is required when mpesa_mode is PHONE")
        if mode == "TILL" and not till:
            raise ValueError("mpesa_till_number is required when mpesa_mode is TILL")
        if mode == "POCHI" and not pochi:
            raise ValueError("pochi_phone is required when mpesa_mode is POCHI")

        # Enforce pick-one (only one recipient type field can be provided).
        provided = [
            bool(self.mpesa_phone and str(self.mpesa_phone).strip()),
            bool(self.mpesa_till_number and str(self.mpesa_till_number).strip()),
            bool(self.pochi_phone and str(self.pochi_phone).strip()),
        ]
        if sum(provided) > 1:
            raise ValueError(
                "Provide only one of mpesa_phone, mpesa_till_number, or pochi_phone"
            )

        self.mpesa_mode = mode
        self.mpesa_phone = phone
        self.mpesa_till_number = till
        self.pochi_phone = pochi




class MerchantEarningsResponse(BaseModel):
    available_balance: float
    pending_balance: float
    currency: str

