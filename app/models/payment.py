from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from datetime import datetime, timezone
from app.db.base import Base, TimestampMixin


class PaymentStatus(str, enum.Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class Payment(Base, TimestampMixin):
    __tablename__ = 'payments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey('orders.id'), nullable=True)
    provider = Column(String(50), nullable=False)
    provider_transaction_id = Column(String(255), nullable=True, unique=True)
    status = Column(String(20), nullable=False, default='pending')
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), default='KES', nullable=False)
    phone = Column(String(20), nullable=True)
    checkout_request_id = Column(String(255), nullable=True, unique=True, index=True)
    mpesa_receipt = Column(String(100), nullable=True)
    result_code = Column(String(10), nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
