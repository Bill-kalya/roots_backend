from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from datetime import datetime, timezone
from app.db.base import Base


class PayoutStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Payout(Base):
    __tablename__ = "payouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="KES", nullable=False)

    status = Column(String(20), default=PayoutStatus.PENDING.value, nullable=False)

    payout_method = Column(String(30), nullable=True)
    recipient_detail = Column(String(255), nullable=True)

    mpesa_conversation_id = Column(String(255), nullable=True)
    mpesa_receipt = Column(String(100), nullable=True)
    provider_payout_id = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_payouts_merchant_id", "merchant_id"),
        Index("idx_payouts_status", "status"),
    )
