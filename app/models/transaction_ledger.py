from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from datetime import datetime, timezone
from app.db.base import Base


class EntryType(str, enum.Enum):
    CREDIT_PENDING = "CREDIT_PENDING"
    ESCROW_RELEASE = "ESCROW_RELEASE"
    PAYOUT_REQUEST = "PAYOUT_REQUEST"
    PAYOUT_COMPLETED = "PAYOUT_COMPLETED"
    PAYOUT_FAILED = "PAYOUT_FAILED"
    COMMISSION = "COMMISSION"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionLedger(Base):
    __tablename__ = "transaction_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("merchant_wallets.id"), nullable=True)

    amount = Column(Numeric(12, 2), nullable=False)
    entry_type = Column(String(20), nullable=False)
    currency = Column(String(3), default="KES", nullable=False)

    reference_id = Column(String(255), nullable=True)
    reference_type = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)

    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_ledger_merchant_id", "merchant_id"),
        Index("idx_ledger_created_at", "created_at"),
        Index("idx_ledger_actor_id", "actor_id"),
    )
