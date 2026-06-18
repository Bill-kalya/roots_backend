import uuid
import enum
from sqlalchemy import Column, String, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, TimestampMixin


class MerchantPayoutMethod(str, enum.Enum):
    MPESA = "MPESA"
    PAYPAL = "PAYPAL"
    STRIPE = "STRIPE"


class MerchantPayoutSettings(Base, TimestampMixin):
    __tablename__ = "merchant_payout_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # One payout settings record per merchant.
    merchant_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)

    payout_method = Column(String(30), nullable=False)

    mpesa_phone = Column(String(20), nullable=True)
    paypal_email = Column(String(255), nullable=True)
    stripe_account_id = Column(String(255), nullable=True)

    is_verified = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_merchant_payout_settings_merchant_id", "merchant_id"),
    )

