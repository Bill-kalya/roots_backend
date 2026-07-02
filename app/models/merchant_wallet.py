from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from app.db.base import Base, TimestampMixin


class MerchantWallet(Base, TimestampMixin):
    __tablename__ = "merchant_wallets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)

    available_balance = Column(Numeric(12, 2), default=0.00, nullable=False)
    pending_balance = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_earned = Column(Numeric(14, 2), default=0.00, nullable=False)
    total_withdrawn = Column(Numeric(14, 2), default=0.00, nullable=False)

    currency = Column(String(3), default="KES", nullable=False)

    __table_args__ = (
        Index("idx_merchant_wallets_merchant_id", "merchant_id"),
    )
